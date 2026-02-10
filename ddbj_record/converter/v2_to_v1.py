from __future__ import annotations

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


def v2_to_v1(v2_obj: DdbjRecordV2) -> DdbjRecordV1:
    return DdbjRecordV1(
        schema_version="v1.0",
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
    dblink: Dblink | None = None
    if dblink_project or dblink_biosample or dblink_sra:
        dblink = Dblink.model_construct(
            project=dblink_project,
            biosample=dblink_biosample,
            sequence_read_archive=dblink_sra or None,
        )

    # SUBMITTER
    ab_names: list[str] = [s.abbreviation for s in v2_obj.submission.submitters if s.abbreviation]
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
            for organization_obj in contact_person.organization:
                if organization_obj.type == "institution":
                    institute = organization_obj.name
                    url = organization_obj.url
                    department = organization_obj.department
                    if organization_obj.address:
                        country = organization_obj.address.country
                        state = organization_obj.address.state or ""
                        city = organization_obj.address.city
                        street = organization_obj.address.street or ""
                        zip_code = organization_obj.address.postal_code or ""
                elif organization_obj.type == "consortium":
                    consrtm = organization_obj.name

    submitter = Submitter.model_construct(
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
    references: list[Reference] = []
    for ref in v2_obj.submission.references:
        ref_ab_names: list[str] = [author.abbreviation for author in ref.authors if author.abbreviation]
        references.append(
            Reference.model_construct(
                title=ref.title,
                ab_name=ref_ab_names,
                status=" ".join(ref.status.split("-")).title(),
                year=ref.year,
            )
        )

    # COMMENT
    comments: list[Comment] = (
        [Comment.model_construct(line=line) for line in v2_obj.submission.comments]
        if v2_obj.submission.comments
        else []
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
    st_comment = StComment.model_construct(
        tagset_id=tagset_id,
        assembly_method=assembly_method,
        coverage=coverage,
        genome_coverage=genome_coverage,
        sequencing_technology=sequencing_technology,
    )

    # DATE
    date = None
    if v2_obj.submission.hold_date:
        date = Date.model_construct(hold_date=v2_obj.submission.hold_date)

    # trad_submission_category
    trad_submission_category = v2_obj.submission.trad_submission_category or "GNM"

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
        if len(q_objs) == 1:
            common_source_obj[key] = _qualifier_value_to_union(q_objs[0].value)
        if len(q_objs) > 1:  # if key is 'note', value is List[str]
            common_source_obj[key] = [_qualifier_value_to_union(q_obj.value) for q_obj in q_objs]

    return CommonSource(**common_source_obj)


def _convert_common_meta(v2_obj: DdbjRecordV2) -> CommonMeta:
    return CommonMeta(
        division=v2_obj.submission.division or "BCT",
        locus_tag_prefix=v2_obj.submission.locus_tag_prefix,
        dfast_version=getattr(v2_obj.provenance, "dfast_version", None),
        seq_prefix=v2_obj.submission.seq_prefix,
    )


def _convert_entries(v2_obj: DdbjRecordV2) -> list[Entry]:
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

        # Add COMMENT feature from v2 entry
        if v2_entry.comments:
            for i, line in enumerate(v2_entry.comments):
                v1_entry.features.append(
                    Feature(
                        id=f"{v2_entry.id}_comment_{i + 1}",
                        type="comment",
                        location="",
                        qualifiers={"line": line},
                    )
                )

        entries.append(v1_entry)

    return entries
