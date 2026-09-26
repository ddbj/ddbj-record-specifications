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
#   DIR/fingerprint.json   which database it was read from
#
# Only accessions that have been numbered: a submission not yet given one is still being made,
# and is not migrated. The files hold what the database holds, byte for byte.
#
# Read-only. Keyset pagination on metadata_id, a few rows a page: an ADF runs to hundreds of
# megabytes, and a single cursor would hold one snapshot for the whole read.

require 'bundler/inline'

gemfile do
  source 'https://rubygems.org'

  gem 'pg'
end

require 'fileutils'
require 'json'

DIR  = ARGV.fetch(0)
PAGE = 20

EXTENSIONS = {1 => 'idf.txt', 2 => 'sdrf.txt', 3 => 'adf'}

conn = PG.connect
conn.exec 'SET default_transaction_read_only = on'
conn.exec "SET statement_timeout = '5min'"
# The text as stored, not decoded: which encoding it is in is for the census to find out.
conn.exec 'SET client_encoding = SQL_ASCII'

fingerprint = conn.exec(<<~SQL).first
  SELECT current_database() AS database, inet_server_addr()::text AS server_addr, inet_server_port() AS server_port,
         version() AS server_version
SQL

FileUtils.mkdir_p DIR
File.write File.join(DIR, 'fingerprint.json'), JSON.pretty_generate(fingerprint)

last    = 0
written = Hash.new(0)

loop do
  rows = conn.exec_params(<<~SQL, [last, PAGE]).to_a
    SELECT m.metadata_id, a.accession, m.metadata_type, m.metadata_version, m.metadata
    FROM mass.metadata m JOIN mass.accession a USING (accession_id)
    WHERE m.metadata_id > $1 AND a.accession IS NOT NULL
    ORDER BY m.metadata_id
    LIMIT $2
  SQL
  break if rows.empty?

  rows.each do |row|
    extension = EXTENSIONS.fetch(row['metadata_type'].to_i)
    kind      = extension.delete_suffix('.txt')
    dir       = File.join(DIR, kind, row['accession'])

    FileUtils.mkdir_p dir
    File.binwrite File.join(dir, "#{row['accession']}_v#{row['metadata_version']}.#{extension}"), row['metadata'].to_s
    written[kind] += 1
  end

  last = rows.last['metadata_id'].to_i
end

puts JSON.generate(written)
