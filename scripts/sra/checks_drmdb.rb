# The figures docs/v3-sra.md cites that the census does not produce.
#
#   PGHOST=... PGPORT=... PGUSER=... PGPASSWORD=... PGDATABASE=drmdb \
#     ruby scripts/sra/checks_drmdb.rb OUT.json
#
# 1. How many objects of each kind D-way has issued an accession for.
# 2. Stored documents that are not well-formed XML (the parser recovers them, so the census
#    only shows them as odd paths).
# 3. *_ATTRIBUTE elements whose TAG is empty: does any of them carry a VALUE or UNITS?
#    (Attribute.name is required in v3.)
# 4. How many studies one submission refers to, counted two ways: by the study accessions in its
#    experiments' STUDY_REF, and by the submission-to-study parent links in
#    mass.accession_relation. (v3 has one project per record.)
# 5. Objects of one kind in one submission that share an alias.
#    (Whether alias can identify a relation's source.)
#
# Read-only. The scans of mass.meta_entity go in meta_id ranges, each well inside the statement
# timeout. OUT is rewritten after each part, so a failure keeps what came before it.

require 'bundler/inline'

gemfile do
  source 'https://rubygems.org'

  gem 'nokogiri'
  gem 'pg'
end

require 'json'
require 'set'

OUT   = ARGV.fetch(0)
RANGE = 250_000

conn = PG.connect
conn.type_map_for_results = PG::BasicTypeMapForResults.new(conn)
conn.exec 'SET default_transaction_read_only = on'
conn.exec "SET statement_timeout = '3min'"

out = {
  'fingerprint' => conn.exec(<<~SQL).first
    SELECT current_database() AS database, inet_server_addr()::text AS server_addr, inet_server_port() AS server_port,
           version() AS server_version
  SQL
}

save = -> { File.write OUT, JSON.pretty_generate(out) }

max_meta_id = conn.exec('SELECT max(meta_id) FROM mass.meta_entity').getvalue(0, 0)

# Each part below scans mass.meta_entity in meta_id ranges.
each_range = lambda do |&block|
  (0..max_meta_id).step(RANGE) do |from|
    block.call from, from + RANGE
  end
end

# --- 1

out['accessions'] = conn.exec(<<~SQL).to_h { [it['acc_type'], it['count']] }
  SELECT acc_type, count(*) FROM mass.accession_entity WHERE NOT is_delete GROUP BY 1 ORDER BY 1
SQL
save.call

# --- 2

not_well_formed = Hash.new {|h, k| h[k] = {'documents' => 0, 'examples' => []} }

each_range.call do |from, to|
  rows = conn.exec_params(<<~SQL, [from, to])
    SELECT meta_id, type FROM mass.meta_entity
    WHERE meta_id > $1 AND meta_id <= $2 AND NOT xml_is_well_formed_document(content)
  SQL

  rows.each do |row|
    tally = not_well_formed[row['type']]

    tally['documents'] += 1
    tally['examples'] << row['meta_id'] if tally['examples'].size < 10
  end
end

out['not_well_formed'] = not_well_formed
save.call

# --- 3

empty_tags = Hash.new {|h, k| h[k] = {'documents' => 0, 'attributes' => 0, 'with_value' => 0, 'examples' => []} }

each_range.call do |from, to|
  rows = conn.exec_params(<<~SQL, [from, to])
    SELECT meta_id, type, content FROM mass.meta_entity
    WHERE meta_id > $1 AND meta_id <= $2 AND content ~ '<TAG>[[:space:]]*</TAG>|<TAG[[:space:]]*/>'
  SQL

  rows.each do |row|
    tally = empty_tags[row['type']]
    hit   = false

    Nokogiri::XML(row['content']) { it.nonet }.xpath('//*[TAG]').each do |attr|
      next unless attr.at_xpath('TAG').text.strip.empty?

      hit = true
      tally['attributes'] += 1

      rest = %w[VALUE UNITS].filter_map { attr.at_xpath(it)&.text&.strip }.reject(&:empty?)
      next if rest.empty?

      tally['with_value'] += 1
      tally['examples'] << row['meta_id'] if tally['examples'].size < 10
    end

    tally['documents'] += 1 if hit
  end
end

out['empty_tags'] = empty_tags
save.call

# --- 4

# Only study accessions count: an experiment may name the same study by refname where another
# names it by accession, and counting both would make one study two. Experiments that name
# their study by refname alone are counted separately.
studies    = Hash.new {|h, k| h[k] = Set.new }
by_refname = 0
last       = [0, 0]

loop do
  rows = conn.exec_params(<<~SQL, last).to_a
    WITH x AS (
      SELECT r.p_acc_id AS submission, c.acc_id
      FROM mass.accession_relation r
      JOIN mass.accession_entity c ON c.acc_id = r.acc_id AND c.acc_type = 'DRX' AND NOT c.is_delete
      JOIN mass.accession_entity p ON p.acc_id = r.p_acc_id AND p.acc_type = 'DRA' AND NOT p.is_delete
      WHERE (c.acc_id, r.p_acc_id) > ($1::bigint, $2::bigint)
      ORDER BY c.acc_id, r.p_acc_id
      LIMIT 20000
    ), latest AS (
      SELECT DISTINCT ON (m.acc_id) m.acc_id, m.content
      FROM mass.meta_entity m
      WHERE m.acc_id IN (SELECT acc_id FROM x)
      ORDER BY m.acc_id, m.meta_version DESC
    )
    SELECT x.submission, x.acc_id,
           substring(latest.content from '<STUDY_REF[^>]*[[:space:]]accession="([^"]+)"') AS accession
    FROM x JOIN latest USING (acc_id)
    ORDER BY x.acc_id, x.submission
  SQL
  break if rows.empty?

  rows.each do |row|
    if row['accession']
      studies[row['submission']] << row['accession']
    else
      by_refname += 1
    end
  end

  last = rows.last.values_at('acc_id', 'submission')
end

by_parent_link = conn.exec(<<~SQL).to_h { [it['studies'], it['submissions']] }
  WITH per AS (
    SELECT r.p_acc_id, count(DISTINCT c.acc_id) AS n
    FROM mass.accession_relation r
    JOIN mass.accession_entity c ON c.acc_id = r.acc_id AND NOT c.is_delete AND c.acc_type = 'DRP'
    JOIN mass.accession_entity p ON p.acc_id = r.p_acc_id AND NOT p.is_delete AND p.acc_type = 'DRA'
    GROUP BY 1
  )
  SELECT n::int AS studies, count(*)::int AS submissions FROM per GROUP BY 1 ORDER BY 1
SQL

out['studies_per_submission'] = {
  'by_study_ref_accession' => studies.values.map(&:size).tally.sort.to_h,
  'experiments_naming_their_study_by_refname_only' => by_refname,
  'by_parent_link' => by_parent_link
}
save.call

# --- 5

out['shared_aliases'] = conn.exec(<<~SQL).to_a
  WITH members AS (
    SELECT r.p_acc_id AS submission, c.acc_type, c.alias, c.acc_id
    FROM mass.accession_relation r
    JOIN mass.accession_entity c ON c.acc_id = r.acc_id AND NOT c.is_delete
    JOIN mass.accession_entity p ON p.acc_id = r.p_acc_id AND NOT p.is_delete AND p.acc_type = 'DRA'
  ), shared AS (
    SELECT submission, acc_type, alias, count(DISTINCT acc_id) AS n
    FROM members GROUP BY 1, 2, 3 HAVING count(DISTINCT acc_id) > 1
  )
  SELECT acc_type, count(DISTINCT submission)::int AS submissions, count(*)::int AS aliases, max(n)::int AS most_objects
  FROM shared GROUP BY 1 ORDER BY 1
SQL
save.call
