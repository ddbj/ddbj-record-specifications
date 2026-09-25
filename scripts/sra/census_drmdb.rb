# Every element and attribute path in every DRA metadata document D-way has stored.
#
# The second of the three steps that produce docs/v3-sra-mapping.yml (see scripts/sra/README.md).
#
#   PGHOST=... PGPORT=... PGUSER=... PGPASSWORD=... PGDATABASE=drmdb \
#     ruby scripts/sra/census_drmdb.rb OUT.json
#
# Reads mass.meta_entity (all versions of all documents) and records, per document type and
# path: how many documents contain it, whether it holds text, how often it repeats under one
# parent, a few of its values, and which kinds of value it holds (int / float / bool / empty /
# str) — a field can be typed in v3 only if every stored value reads as that type.
#
# The output holds sample values (names, e-mail addresses), so it is not committed; only the
# paths and counts go into the mapping.
#
# Read-only. Keyset pagination on meta_id, one short statement per page: a single cursor would
# hold one snapshot for the whole scan and keep vacuum from reclaiming anything for its duration.
# Checkpoints the tally, so a dropped connection resumes rather than restarts.

require 'bundler/inline'

gemfile do
  source 'https://rubygems.org'

  gem 'nokogiri'
  gem 'pg'
end

require 'json'
require 'set'
require 'time'

OUT           = ARGV.fetch(0)
PAGE          = 2_000
CHECKPOINT    = 250_000
SAMPLES       = 30
KIND_EXAMPLES = 5

conn = PG.connect
conn.type_map_for_results = PG::BasicTypeMapForResults.new(conn)
conn.exec 'SET default_transaction_read_only = on'
conn.exec "SET statement_timeout = '2min'"

fingerprint = conn.exec(<<~SQL).first
  SELECT current_database() AS database, inet_server_addr()::text AS server_addr, inet_server_port() AS server_port,
         version() AS server_version,
         (SELECT reltuples::bigint FROM pg_class WHERE oid = 'mass.meta_entity'::regclass) AS estimated_rows
SQL

state = if File.exist?(OUT)
  JSON.parse(File.read(OUT))
else
  {'fingerprint' => fingerprint, 'last_meta_id' => 0, 'rows' => 0, 'documents' => {}, 'paths' => {}, 'not_well_formed' => {}}
end

same_database = %w[database server_addr server_port].all? { state['fingerprint'][it] == fingerprint[it] }
abort "#{OUT} was taken from another database: #{state['fingerprint']}" unless same_database

def kind_of(value)
  case value
  when ''                                                 then 'empty'
  when /\A[+-]?\d+\z/                                     then 'int'
  when /\A[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?\z/ then 'float'
  when /\A(?:true|false)\z/                               then 'bool'
  else 'str'
  end
end

# Paths in one document: which occur, which hold text, how often each repeats under one parent,
# and the values seen. An element that is present but says nothing is recorded as the value ''.
def walk(node, path, seen, text_paths, repeats, values)
  seen << path

  node.attribute_nodes.each do |attr|
    apath = "#{path}/@#{attr.name}"

    seen << apath
    (values[apath] ||= Set.new) << attr.value
  end

  content = node.children.select { it.text? || it.cdata? }.map(&:content).join.strip

  if !content.empty?
    text_paths << path
    (values[path] ||= Set.new) << content
  elsif node.element_children.empty?
    (values[path] ||= Set.new) << ''
  end

  node.element_children.group_by(&:name).each do |name, children|
    cpath = "#{path}/#{name}"

    repeats[cpath] = [repeats.fetch(cpath, 0), children.size].max
    children.each do |child|
      walk child, cpath, seen, text_paths, repeats, values
    end
  end
end

def save(state, out)
  File.write("#{out}.tmp", JSON.generate(state))
  File.rename("#{out}.tmp", out)
end

started = Time.now
since   = state['rows']

loop do
  rows = conn.exec_params(<<~SQL, [state['last_meta_id'], PAGE]).to_a
    SELECT meta_id, type, content FROM mass.meta_entity WHERE meta_id > $1 ORDER BY meta_id LIMIT $2
  SQL
  break if rows.empty?

  rows.each do |row|
    type = row['type'].to_s
    doc  = Nokogiri::XML(row['content'].to_s) { it.nonet }

    # Not well-formed: the parser recovers what it can, and the paths below are what it made of
    # the document. Recorded so those paths can be told from ones a schema had.
    if doc.errors.any?
      tally = (state['not_well_formed'][type] ||= {'documents' => 0, 'examples' => []})

      tally['documents'] += 1
      tally['examples'] << row['meta_id'] if tally['examples'].size < 10
    end

    root = doc.root
    next if root.nil?

    seen    = Set.new
    text    = Set.new
    repeats = {}
    values  = {}

    walk root, root.name, seen, text, repeats, values

    state['documents'][type] = state['documents'].fetch(type, 0) + 1
    by_type = (state['paths'][type] ||= {})

    seen.each do |path|
      entry = (by_type[path] ||= {'docs' => 0, 'text' => false, 'max_repeat' => 1, 'example' => row['meta_id']})
      entry['docs'] += 1
    end

    text.each do |path|
      by_type[path]['text'] = true
    end

    repeats.each do |path, n|
      entry = by_type[path]
      next unless n > entry['max_repeat']

      entry['max_repeat']     = n
      entry['repeat_example'] = row['meta_id']
    end

    values.each do |path, vs|
      entry  = by_type[path]
      sample = (entry['values'] ||= [])
      kinds  = (entry['kinds'] ||= {})

      vs.each do |v|
        sample << v if sample.size < SAMPLES && !sample.include?(v) && v.size <= 200

        examples = (kinds[kind_of(v)] ||= [])
        examples << v if examples.size < KIND_EXAMPLES && !examples.include?(v) && v.size <= 200
      end
    end
  end

  state['last_meta_id'] = rows.last['meta_id']
  state['rows']        += rows.size

  next unless (state['rows'] % CHECKPOINT) < PAGE

  save state, OUT
  warn format('%s rows=%d last_meta_id=%d rate=%.0f/s', Time.now.strftime('%H:%M:%S'), state['rows'], state['last_meta_id'], (state['rows'] - since) / (Time.now - started))
end

state['finished_at'] = Time.now.utc.iso8601
save state, OUT
warn "done: #{state['rows']} rows, #{state['documents'].inspect}, not well-formed #{state['not_well_formed'].inspect}"
