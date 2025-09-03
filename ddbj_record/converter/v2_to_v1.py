from typing import Dict, List, Union

from ddbj_record.schema.v1 import (Comment, Common, CommonMeta, CommonSource,
                                   Date, Dblink)
from ddbj_record.schema.v1 import DdbjRecord as DdbjRecordV1
from ddbj_record.schema.v1 import (Entry, Feature, Reference, StComment,
                                   Submitter)
from ddbj_record.schema.v2 import DdbjRecord as DdbjRecordV2


def v2_to_v1(v2_obj: DdbjRecordV2) -> DdbjRecordV1:
    return DdbjRecordV1(
        schema_version="v1",
        COMMON=_convert_common(v2_obj),
        COMMON_SOURCE=_convert_common_source(v2_obj),
        COMMON_META=_convert_common_meta(v2_obj),
        ENTRIES=_convert_entries(v2_obj)
    )


def _qualifier_value_to_union(value: str) -> Union[str, bool]:
    if value == "true":
        return True
    if value == "false":
        return False
    return value


def _convert_common(v2_obj: DdbjRecordV2) -> Common:
    # DBLINK
    db_link_obj = {
        "project": "",
        "biosample": "",
        "sequence_read_archive": [],
    }
    for xref in v2_obj.submission.db_xrefs:
        if xref.db == "bioproject":
            db_link_obj["project"] = xref.id
        elif xref.db == "biosample":
            db_link_obj["biosample"] = xref.id
        elif xref.db == "insdc.sra":
            db_link_obj["sequence_read_archive"].append(xref.id)  # type: ignore
    if all(not v for v in db_link_obj.values()):
        dblink = None
    else:
        dblink = Dblink.model_construct(**db_link_obj)  # type: ignore

    # SUBMITTER
    submitter_obj = {
        "ab_name": [],
        "contact": "",
        "email": "",
        "url": None,
        "institute": "",
        "department": None,
        "country": "",
        "state": "",
        "city": "",
        "street": "",
        "zip": "",
    }
    if v2_obj.submission.submitters:
        first_submitter = v2_obj.submission.submitters[0]
        submitter_obj["contact"] = first_submitter.name or ""
        submitter_obj["email"] = first_submitter.email or ""
        if first_submitter.organization:
            for organization_obj in first_submitter.organization:
                if organization_obj.type == "institution":
                    submitter_obj["institute"] = organization_obj.name
                    submitter_obj["url"] = organization_obj.url
                    submitter_obj["department"] = organization_obj.department
                    if organization_obj.address:
                        submitter_obj["country"] = organization_obj.address.country
                        submitter_obj["state"] = organization_obj.address.state or ""
                        submitter_obj["city"] = organization_obj.address.city
                        submitter_obj["street"] = organization_obj.address.street or ""
                        submitter_obj["zip"] = organization_obj.address.postal_code or ""
                elif organization_obj.type == "consortium":
                    submitter_obj["consrtm"] = organization_obj.name
        for submitter in v2_obj.submission.submitters:
            if submitter.abbreviation:
                submitter_obj["ab_name"].append(submitter.abbreviation)  # type: ignore
    submitter = Submitter.model_construct(**submitter_obj)  # type: ignore

    # REFERENCE
    references: List[Reference] = []
    for ref in v2_obj.submission.references:
        ref_obj = {
            "title": ref.title,
            "ab_name": [],
            "status": " ".join(ref.status.split("-")).title(),
            "year": ref.year,
        }
        for author in ref.authors:
            if author.abbreviation:
                ref_obj["ab_name"].append(author.abbreviation)  # type: ignore
        references.append(Reference.model_construct(**ref_obj))  # type: ignore

    # COMMENT
    comments = []
    if v2_obj.submission.comments:
        for line in v2_obj.submission.comments:
            comments.append(Comment.model_construct(line=line))

    # ST_COMMENT
    st_comment_obj = {
        "tagset_id": "",
        "assembly_method": "",
        "coverage": None,
        "genome_coverage": None,
        "sequencing_technology": "",
    }  # These keys is using pydantic's alias feature
    for exp in v2_obj.experiments:
        if exp.id == "st_comment_experiment":
            if exp.platform and exp.platform.platform_type:
                st_comment_obj["sequencing_technology"] = exp.platform.platform_type
            if "tagset_id" in exp.experiment_attributes:
                st_comment_obj["tagset_id"] = exp.experiment_attributes["tagset_id"]
            if "assembly_method" in exp.experiment_attributes:
                st_comment_obj["assembly_method"] = exp.experiment_attributes["assembly_method"]
            if "coverage" in exp.experiment_attributes:
                st_comment_obj["coverage"] = exp.experiment_attributes["coverage"]
            if "genome_coverage" in exp.experiment_attributes:
                st_comment_obj["genome_coverage"] = exp.experiment_attributes["genome_coverage"]
    st_comment = StComment.model_construct(**st_comment_obj)  # type: ignore

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
    common_source_obj: Dict[str, Union[Union[str, bool], List[Union[str, bool]]]] = {
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

    return CommonSource.model_construct(**common_source_obj)  # type: ignore


def _convert_common_meta(v2_obj: DdbjRecordV2) -> CommonMeta:
    return CommonMeta(
        division=v2_obj.submission.division or "BCT",
        locus_tag_prefix=v2_obj.submission.locus_tag_prefix,
        dfast_version=getattr(v2_obj.provenance, "dfast_version", None),
        seq_prefix=v2_obj.submission.seq_prefix,
    )


def _convert_entries(v2_obj: DdbjRecordV2) -> List[Entry]:
    entries: List[Entry] = []
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
            source_feature = Feature(
                id=v2_sf.id,
                type="source",
                location=v2_sf.location,
                qualifiers={},
                locus_tag_id=None,  # source feature does not have locus_tag_id
            )
            if v2_sf.source:
                source_feature.qualifiers["organism"] = [v2_sf.source.organism]
                source_feature.qualifiers["mol_type"] = [v2_sf.source.mol_type]
                for key, q_objs in v2_sf.source.qualifiers.items():
                    if key in ("organism", "mol_type"):
                        continue
                    source_feature.qualifiers[key] = []
                    for q_obj in q_objs:
                        source_feature.qualifiers[key].append(_qualifier_value_to_union(q_obj.value))
            if v2_sf.definition:
                source_feature.qualifiers["ff_definition"] = v2_sf.definition  # type: ignore
            v1_entry.features.append(source_feature)  # pylint: disable=no-member

        # Add COMMENT feature from v2 entry
        if v2_entry.comments:
            for i, line in enumerate(v2_entry.comments):
                v1_entry.features.append(Feature(  # pylint: disable=no-member
                    id=f"{v2_entry.id}_comment_{i+1}",
                    type="comment",
                    location="",
                    qualifiers={"line": line},
                ))

        entries.append(v1_entry)

    return entries
