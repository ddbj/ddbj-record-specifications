from __future__ import annotations

import warnings

from ddbj_record.schema import LATEST_MINOR_VERSIONS
from ddbj_record.schema.v1 import (
    Comment,
    Common,
    CommonMeta,
    CommonSource,
    Date,
    Dblink,
    Entry,
    Feature,
    Reference,
    StComment,
    Submitter,
)
from ddbj_record.schema.v1 import DdbjRecord as DdbjRecordV1
from ddbj_record.schema.v2 import DdbjRecord as DdbjRecordV2
from ddbj_record.schema.v2 import Person as V2Person


def _warn_data_loss(msg: str) -> None:
    warnings.warn(msg, UserWarning, stacklevel=3)


def v2_to_v1(v2_obj: DdbjRecordV2) -> DdbjRecordV1:
    return DdbjRecordV1(
        schema_version=LATEST_MINOR_VERSIONS["v1"],
        COMMON=_convert_common(v2_obj),
        COMMON_SOURCE=_convert_common_source(v2_obj),
        COMMON_META=_convert_common_meta(v2_obj),
        ENTRIES=_convert_entries(v2_obj),
    )


def _qualifier_value_to_union(value: str) -> str | bool:
    if value == "true":
        return True
    if value == "false":
        return False

    return value


def _convert_common(v2_obj: DdbjRecordV2) -> Common:
    # DBLINK
    dblink_project = ""
    dblink_biosample = ""
    dblink_sra: list[str] = []
    for xref in v2_obj.submission.db_xrefs:
        if xref.db == "bioproject":
            dblink_project = xref.id
        elif xref.db == "biosample":
            dblink_biosample = xref.id
        elif xref.db == "insdc.sra":
            dblink_sra.append(xref.id)
        else:
            _warn_data_loss(f"db_xref with db='{xref.db}' ignored during v2 to v1 conversion")
    dblink: Dblink | None = None
    if dblink_project or dblink_biosample or dblink_sra:
        dblink = Dblink(
            project=dblink_project,
            biosample=dblink_biosample,
            **{"sequence read archive": dblink_sra or None},
        )

    # SUBMITTER
    ab_names: list[str] = [s.abbreviation for s in v2_obj.submission.submitters if s.abbreviation]

    # Warn for submitters without abbreviation
    for s in v2_obj.submission.submitters:
        if not s.abbreviation and s.name:
            _warn_data_loss(f"submitter name without abbreviation will not appear in v1 ab_name: '{s.name}'")
        if s.orcid:
            _warn_data_loss(f"orcid '{s.orcid}' ignored during v2 to v1 conversion")

    contact = ""
    email = ""
    url: str | None = None
    institute = ""
    department: str | None = None
    consrtm: str | None = None
    country = ""
    state = ""
    city = ""
    street = ""
    zip_code = ""

    def _pick_contact_person(submitters: list[V2Person]) -> V2Person | None:
        if not submitters:
            return None
        # name and email
        both = [s for s in submitters if s.name and s.email]
        if both:
            return both[0]
        # with email
        with_email = [s for s in submitters if s.email]
        if with_email:
            return with_email[0]
        # organization
        with_org = [s for s in submitters if s.organization]
        if with_org:
            return with_org[0]
        # first one (fallback)

        return submitters[0]

    contact_person = _pick_contact_person(v2_obj.submission.submitters)
    if contact_person:
        contact = contact_person.name or ""
        email = contact_person.email or ""
        if contact_person.organization:
            institution_count = 0
            consortium_count = 0
            for organization_obj in contact_person.organization:
                if organization_obj.type == "institution":
                    institution_count += 1
                    if institution_count == 1:
                        institute = organization_obj.name
                        url = organization_obj.url
                        department = organization_obj.department
                        if organization_obj.address:
                            country = organization_obj.address.country
                            state = organization_obj.address.state or ""
                            city = organization_obj.address.city
                            street = organization_obj.address.street or ""
                            zip_code = organization_obj.address.postal_code or ""
                    else:
                        _warn_data_loss(
                            f"additional institution '{organization_obj.name}' ignored during v2 to v1 conversion"
                        )
                elif organization_obj.type == "consortium":
                    consortium_count += 1
                    consrtm = organization_obj.name
                    if consortium_count > 1:
                        _warn_data_loss(
                            f"additional consortium '{organization_obj.name}' ignored; "
                            "only last consortium is preserved in v1"
                        )
                if organization_obj.ror_id:
                    _warn_data_loss(f"ror_id '{organization_obj.ror_id}' ignored during v2 to v1 conversion")

    # Warn for non-contact submitter organizations
    for _i, s in enumerate(v2_obj.submission.submitters):
        if s != contact_person and s.organization:
            _warn_data_loss(
                f"organization info from non-contact submitter '{s.abbreviation or s.name}' "
                "ignored during v2 to v1 conversion"
            )

    submitter = Submitter(
        ab_name=ab_names,
        contact=contact,
        email=email,
        url=url,
        institute=institute,
        department=department,
        consrtm=consrtm,
        country=country,
        state=state,
        city=city,
        street=street,
        zip=zip_code,
    )

    # REFERENCE
    ignored_ref_fields = (
        "journal",
        "volume",
        "issue",
        "start_page",
        "end_page",
        "date_published",
        "doi",
        "url",
        "pubmed_id",
    )
    references: list[Reference] = []
    for ref in v2_obj.submission.references:
        ref_ab_names: list[str] = []
        for author in ref.authors:
            if author.abbreviation:
                ref_ab_names.append(author.abbreviation)
            if author.name or author.email or author.orcid or author.organization:
                _warn_data_loss(
                    "author name/email/orcid/organization ignored during v2 to v1 conversion "
                    "(only abbreviation is preserved)"
                )
        if ref.consortiums:
            _warn_data_loss("reference consortiums ignored during v2 to v1 conversion")
        for field_name in ignored_ref_fields:
            if getattr(ref, field_name, None) is not None:
                _warn_data_loss(f"reference field '{field_name}' ignored during v2 to v1 conversion")
        references.append(
            Reference(
                title=ref.title,
                ab_name=ref_ab_names,
                status=" ".join(ref.status.split("-")).title(),
                year=ref.year,
            )
        )

    # COMMENT
    comments: list[Comment] = (
        [Comment(line=line) for line in v2_obj.submission.comments] if v2_obj.submission.comments else []
    )

    # ST_COMMENT
    tagset_id = ""
    assembly_method = ""
    coverage: str | None = None
    genome_coverage: str | None = None
    sequencing_technology = ""
    for exp in v2_obj.experiments:
        if exp.id == "st_comment_experiment":
            if exp.platform and exp.platform.platform_type:
                sequencing_technology = exp.platform.platform_type
            if "tagset_id" in exp.experiment_attributes:
                tagset_id = exp.experiment_attributes["tagset_id"]
            if "assembly_method" in exp.experiment_attributes:
                assembly_method = exp.experiment_attributes["assembly_method"]
            if "coverage" in exp.experiment_attributes:
                coverage = exp.experiment_attributes["coverage"]
            if "genome_coverage" in exp.experiment_attributes:
                genome_coverage = exp.experiment_attributes["genome_coverage"]
            if exp.title:
                _warn_data_loss("experiment title ignored during v2 to v1 conversion")
            if exp.design:
                _warn_data_loss("experiment design ignored during v2 to v1 conversion")
        else:
            _warn_data_loss(f"experiment '{exp.id}' ignored during v2 to v1 conversion (only st_comment_experiment)")
    st_comment_kwargs: dict[str, str] = {
        "tagset_id": tagset_id,
        "Assembly Method": assembly_method,
        "Sequencing Technology": sequencing_technology,
    }
    if coverage is not None:
        st_comment_kwargs["Coverage"] = coverage
    if genome_coverage is not None:
        st_comment_kwargs["Genome Coverage"] = genome_coverage
    st_comment = StComment(**st_comment_kwargs)

    # DATE
    date = None
    if v2_obj.submission.hold_date:
        date = Date(hold_date=v2_obj.submission.hold_date)

    # trad_submission_category
    trad_submission_category = v2_obj.submission.trad_submission_category
    if trad_submission_category is None:
        _warn_data_loss("trad_submission_category is None, defaulting to 'GNM'")
        trad_submission_category = "GNM"
    elif trad_submission_category not in ("WGS", "GNM"):
        _warn_data_loss(
            f"trad_submission_category '{trad_submission_category}' is not a valid v1 value "
            "(expected 'WGS' or 'GNM'), defaulting to 'GNM'"
        )
        trad_submission_category = "GNM"

    return Common(
        DBLINK=dblink,
        SUBMITTER=submitter,
        REFERENCE=references,
        COMMENT=comments,
        ST_COMMENT=st_comment,
        DATE=date,
        trad_submission_category=trad_submission_category,
    )


def _convert_common_source(v2_obj: DdbjRecordV2) -> CommonSource:
    common_source_obj: dict[str, str | bool | list[str | bool]] = {
        "organism": v2_obj.sequences.common_source.organism,
        "mol_type": v2_obj.sequences.common_source.mol_type,
    }
    for key, q_objs in v2_obj.sequences.common_source.qualifiers.items():
        if key in ("organism", "mol_type"):
            continue
        for q_obj in q_objs:
            if q_obj.id is not None:
                _warn_data_loss(f"qualifier id '{q_obj.id}' ignored during v2 to v1 conversion")
        if len(q_objs) == 1:
            common_source_obj[key] = _qualifier_value_to_union(q_objs[0].value)
        if len(q_objs) > 1:  # if key is 'note', value is List[str]
            common_source_obj[key] = [_qualifier_value_to_union(q_obj.value) for q_obj in q_objs]

    return CommonSource(**common_source_obj)


def _convert_common_meta(v2_obj: DdbjRecordV2) -> CommonMeta:
    division = v2_obj.submission.division
    if division is None:
        _warn_data_loss("division is None, defaulting to 'BCT'")
        division = "BCT"

    # Warn for provenance fields other than dfast_version
    if v2_obj.provenance.source_format is not None:
        _warn_data_loss("provenance field 'source_format' ignored during v2 to v1 conversion")
    for extra_key in v2_obj.provenance.model_extra or {}:
        if extra_key != "dfast_version":
            _warn_data_loss(f"provenance field '{extra_key}' ignored during v2 to v1 conversion")

    return CommonMeta(
        division=division,
        locus_tag_prefix=v2_obj.submission.locus_tag_prefix,
        dfast_version=getattr(v2_obj.provenance, "dfast_version", None),
        seq_prefix=v2_obj.submission.seq_prefix,
    )


def _convert_entries(v2_obj: DdbjRecordV2) -> list[Entry]:
    # Build a mapping from sequence_id to v2 features (CDS, gene, rRNA, etc.)
    features_by_seq_id: dict[str, list[Feature]] = {}
    for v2_feat in v2_obj.features:
        # Warn for qualifier IDs
        for q_objs in v2_feat.qualifiers.values():
            for q_obj in q_objs:
                if q_obj.id is not None:
                    _warn_data_loss(f"qualifier id '{q_obj.id}' ignored during v2 to v1 conversion")
        v1_feat = Feature(
            id=v2_feat.id,
            type=v2_feat.type,
            location=v2_feat.location,
            qualifiers={
                key: [_qualifier_value_to_union(q_obj.value) for q_obj in q_objs]
                for key, q_objs in v2_feat.qualifiers.items()
            },
            locus_tag_id=v2_feat.locus_tag_id,
        )
        features_by_seq_id.setdefault(v2_feat.sequence_id, []).append(v1_feat)

    entries: list[Entry] = []
    for v2_entry in v2_obj.sequences.entries:
        v1_entry = Entry(
            id=v2_entry.id,
            name=v2_entry.name,
            type=v2_entry.type,
            topology=v2_entry.topology,
            sequence=v2_entry.sequence,
            features=[],
        )

        # Add source feature from v2 entry
        for v2_sf in v2_entry.source_features:
            source_qualifiers: dict[str, list[str | bool]] = {}
            if v2_sf.source:
                source_qualifiers["organism"] = [v2_sf.source.organism]
                source_qualifiers["mol_type"] = [v2_sf.source.mol_type]
                for key, q_objs in v2_sf.source.qualifiers.items():
                    if key in ("organism", "mol_type"):
                        continue
                    source_qualifiers[key] = [_qualifier_value_to_union(q_obj.value) for q_obj in q_objs]
            if v2_sf.definition:
                source_qualifiers["ff_definition"] = list(v2_sf.definition)
            source_feature = Feature(
                id=v2_sf.id,
                type="source",
                location=v2_sf.location,
                qualifiers=source_qualifiers,
                locus_tag_id=None,
            )
            v1_entry.features.append(source_feature)

        # Add annotation features (CDS, gene, rRNA, etc.) from v2 top-level features
        v1_entry.features.extend(features_by_seq_id.get(v2_entry.id, []))

        # Add COMMENT feature from v2 entry
        if v2_entry.comments:
            for i, line in enumerate(v2_entry.comments):
                v1_entry.features.append(
                    Feature(
                        id=f"{v2_entry.id}_comment_{i + 1}",
                        type="COMMENT",
                        location="",
                        qualifiers={"line": line},
                    )
                )

        entries.append(v1_entry)

    return entries
