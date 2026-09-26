# Every version of every GEA metadata file D-way has stored, written out as files.
#
# The first of the steps that produce docs/v3-gea-mapping.yml (see scripts/gea/README.md).
#
#   PGHOST=... PGPORT=... PGUSER=... PGPASSWORD=... PGDATABASE=dordb \
#     ruby scripts/gea/export_dordb.rb DIR
#
# Reads mass.metadata (the IDF, SDRF and ADF of each accession, one row per version) and writes
#
#   DIR/idf/E-GEAD-1/E-GEAD-1_v1.idf.txt
#   DIR/sdrf/E-GEAD-1/E-GEAD-1_v1.sdrf.txt
#   DIR/adf/A-GEAD-1/A-GEAD-1_v1.adf
#   DIR/versions.tsv       every file written, with its metadata_id and update_date (UTC)
#   DIR/fingerprint.json   which database it was read from, when, and how many files
#
# The version numbers of an accession's IDF and SDRF run separately (one is revised without the
# other); versions.tsv is what orders them against each other. metadata_id is the order they were
# saved in; update_date is not (docs/v3-gea.md).
#
# Only accessions that have been numbered: a submission not yet given one is still being made,
# and is not migrated. The files hold what the database holds, byte for byte. DIR must be empty
# or absent, so that nothing from an earlier run, or another database, is counted with it.
#
# Read-only. The list of versions is read first; then each file on its own, since an ADF runs to
# hundreds of megabytes.

require 'bundler/inline'

gemfile do
  source 'https://rubygems.org'

  gem 'pg'
end

require 'fileutils'
require 'json'

DIR = ARGV.fetch(0)

EXTENSIONS = {1 => 'idf.txt', 2 => 'sdrf.txt', 3 => 'adf'}
# An experiment has an IDF and an SDRF, an array design an ADF.
ACCESSIONS = {1 => /\AE-GEAD-\d+\z/, 2 => /\AE-GEAD-\d+\z/, 3 => /\AA-GEAD-\d+\z/}

abort "#{DIR} is not empty" if Dir.exist?(DIR) && !Dir.empty?(DIR)

conn = PG.connect
conn.exec 'SET default_transaction_read_only = on'
conn.exec "SET statement_timeout = '5min'"
# The text as stored, not decoded: which encoding it is in is for the census to find out.
conn.exec 'SET client_encoding = SQL_ASCII'
conn.exec "SET TimeZone = 'UTC'"

fingerprint = conn.exec(<<~SQL).first
  SELECT current_database() AS database, inet_server_addr()::text AS server_addr, inet_server_port() AS server_port,
         version() AS server_version, current_setting('server_encoding') AS server_encoding, now() AS read_at
SQL

versions = conn.exec(<<~SQL).to_a
  SELECT m.metadata_id, a.accession, m.metadata_type, m.metadata_version, m.update_date
  FROM mass.metadata m JOIN mass.accession a USING (accession_id)
  WHERE a.accession IS NOT NULL
  ORDER BY m.metadata_id
SQL

FileUtils.mkdir_p DIR
written = Hash.new(0)

File.open File.join(DIR, 'versions.tsv'), 'wx' do |manifest|
  manifest.puts %w[metadata_id accession kind version update_date path].join("\t")

  versions.each do |row|
    id, accession, type, version = row.values_at('metadata_id', 'accession', 'metadata_type', 'metadata_version')

    abort "metadata_id #{id}: unexpected type #{type.inspect}" unless EXTENSIONS.key?(type.to_i)
    abort "metadata_id #{id}: unexpected accession #{accession.inspect}" unless ACCESSIONS.fetch(type.to_i).match?(accession)
    abort "metadata_id #{id}: unexpected version #{version.inspect}" unless version.to_s.match?(/\A[1-9]\d*\z/)

    extension = EXTENSIONS.fetch(type.to_i)
    kind      = extension.delete_suffix('.txt')
    path      = File.join(kind, accession, "#{accession}_v#{version}.#{extension}")

    # The list and the files are read in separate statements; a row that changed in between is not
    # what the list says it is.
    file = conn.exec_params(<<~SQL, [id]).first
      SELECT metadata, metadata_version, update_date FROM mass.metadata WHERE metadata_id = $1
    SQL
    unchanged = file&.values_at('metadata_version', 'update_date') == row.values_at('metadata_version', 'update_date')
    abort "metadata_id #{id} changed while it was read; run again" unless unchanged

    FileUtils.mkdir_p File.join(DIR, File.dirname(path))
    # 'x': two rows naming the same version must not overwrite one another.
    File.open(File.join(DIR, path), 'wbx') { it.write file['metadata'].to_s }
    manifest.puts [id, accession, kind, version, row['update_date'], path].join("\t")
    written[kind] += 1
  end
end

File.write File.join(DIR, 'fingerprint.json'), JSON.pretty_generate(fingerprint.merge('written' => written))
puts JSON.generate(written)
