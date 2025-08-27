from typing import List

from ddbj_record.schema.v1 import DdbjRecord as DdbjRecordV1
from ddbj_record.schema.v2 import Address
from ddbj_record.schema.v2 import DdbjRecord as DdbjRecordV2
from ddbj_record.schema.v2 import (Entry, Experiment, Feature, Organization,
                                   Person, Platform, Provenance, Qualifier,
                                   Reference, Sequences, Source, Submission,
                                   Xref)


def v1_to_v2(v1_obj: DdbjRecordV1) -> DdbjRecordV2:
    return DdbjRecordV2(
        schema_version="v2",
        provenance=_create_provenance(),
        submission=_convert_submission(v1_obj),
        experiments=_convert_experiments(v1_obj),
        sequences=_convert_sequences(v1_obj),
        features=_convert_features(v1_obj)
    )


def _create_provenance() -> Provenance:
    """Create provenance metadata for v2."""
    return Provenance()


def _convert_submission(v1_obj: DdbjRecordV1) -> Submission:
    # === submitters ===
    submitters: List[Person] = []
    organization = Organization(
        name=v1_obj.COMMON.SUBMITTER.institute,
        url=v1_obj.COMMON.SUBMITTER.url,
        address=Address(
            country=v1_obj.COMMON.SUBMITTER.country,
            state=v1_obj.COMMON.SUBMITTER.state,
            city=v1_obj.COMMON.SUBMITTER.city,
            street=v1_obj.COMMON.SUBMITTER.street,
            postal_code=v1_obj.COMMON.SUBMITTER.zip
        ),
    )
    for i, ab_name in enumerate(v1_obj.COMMON.SUBMITTER.ab_name):
        submitters.append(Person(
            name=v1_obj.COMMON.SUBMITTER.contact if i == 0 else None,
            abbreviation=ab_name,
            email=v1_obj.COMMON.SUBMITTER.email if i == 0 else None,
            organization=organization if i == 0 else None,
        ))

    # === db_xrefs ===
    db_xrefs: List[Xref] = [
        Xref(
            db="bioproject",
            id=v1_obj.COMMON.DBLINK.project,
        ),
        Xref(
            db="biosample",
            id=v1_obj.COMMON.DBLINK.biosample,
        )
    ]
    for sra_id in v1_obj.COMMON.DBLINK.sequence_read_archive or []:
        db_xrefs.append(
            Xref(
                db="insdc.sra",
                id=sra_id,
            )
        )

    # === references ===
    references: List[Reference] = []
    for ref in v1_obj.COMMON.REFERENCE:
        references.append(Reference(
            title=ref.title,
            authors=[Person(abbreviation=ab_name) for ab_name in ref.ab_name],
            status=ref.status.lower(),
            year=ref.year,
        ))

    # === comments ===
    comments = []
    for comment in v1_obj.COMMON.COMMENT:
        comments.extend(comment.line)

    return Submission(
        submitters=submitters,
        db_xrefs=db_xrefs,
        references=references,
        comments=comments,
        trad_submission_category=v1_obj.COMMON.trad_submission_category,
        division=v1_obj.COMMON_META.division,
        locus_tag_prefix=v1_obj.COMMON_META.locus_tag_prefix,
        hold_date=v1_obj.COMMON.DATE.hold_date if v1_obj.COMMON.DATE else None,
    )


def _convert_experiments(v1_obj: DdbjRecordV1) -> List[Experiment]:
    return [Experiment(
        id="experiment_1",
        platform=Platform(platform_type=v1_obj.COMMON.ST_COMMENT.sequencing_technology),
        experiment_attributes={
            "tagset_id": v1_obj.COMMON.ST_COMMENT.tagset_id,
            "assembly_method": v1_obj.COMMON.ST_COMMENT.assembly_method,
            "genome_coverage": v1_obj.COMMON.ST_COMMENT.genome_coverage,
        }
    )]


def _convert_sequences(v1_obj: DdbjRecordV1) -> Sequences:
    common_source = Source(
        organism=v1_obj.COMMON_SOURCE.organism,
        mol_type=v1_obj.COMMON_SOURCE.mol_type,
        qualifiers={}
    )
    for key, value in v1_obj.COMMON_SOURCE.model_dump().items():
        if key in ("organism", "mol_type"):
            continue
        if value is not None:
            common_source.qualifiers[key] = [Qualifier(value=value,)]

    entries: List[Entry] = []
    for entry in v1_obj.ENTRIES:
        source_feature = None
        for feature in entry.features:
            if feature.type == "source":
                source_feature = feature
                break
        if source_feature is None:
            continue
        entry_source = None  # source for each entry
        if "organism" in source_feature.qualifiers and "mol_type" in source_feature.qualifiers:
            entry_source = Source(
                organism=source_feature.qualifiers["organism"][0],
                mol_type=source_feature.qualifiers["mol_type"][0],
                qualifiers={}
            )
            for key, value in source_feature.qualifiers.items():
                if key in ("organism", "mol_type"):
                    continue
                entry_source.qualifiers[key] = [Qualifier(value=v) for v in value]
        entry_definition = None  # definition for each entry
        if "ff_definition" in source_feature.qualifiers:
            entry_definition = source_feature.qualifiers["ff_definition"]

        entries.append(Entry(
            id=entry.id,
            name=entry.name,
            type=entry.type,
            topology=entry.topology,
            sequence=entry.sequence,
            location=source_feature.location,
            source=entry_source,
            definition=entry_definition,
        ))

    return Sequences(
        common_source=common_source,
        entries=entries,
    )


def _convert_features(v1_obj: DdbjRecordV1) -> List[Feature]:
    features: List[Feature] = []

    for entry in v1_obj.ENTRIES:
        for feature in entry.features:
            if feature.type == "source":
                continue
            features.append(Feature(
                id=feature.id,
                type=feature.type,
                location=feature.location,
                sequence_id=entry.id,
                qualifiers={
                    key: [Qualifier(value=v) for v in value]
                    for key, value in feature.qualifiers.items()
                },
            ))

    return features
