from __future__ import annotations

import re
import warnings

from ddbj_record.schema import LATEST_MINOR_VERSIONS
from ddbj_record.schema.v1 import DdbjRecord as DdbjRecordV1
from ddbj_record.schema.v1 import Feature as FeatureV1
from ddbj_record.schema.v2 import (
    Address,
    Entry,
    Experiment,
    Feature,
    Organization,
    Person,
    Platform,
    Provenance,
    Qualifier,
    Reference,
    Sequences,
    Source,
    SourceFeature,
    Submission,
    Xref,
)
from ddbj_record.schema.v2 import DdbjRecord as DdbjRecordV2


def v1_to_v2(v1_obj: DdbjRecordV1) -> DdbjRecordV2:
    return DdbjRecordV2(
        schema_version=LATEST_MINOR_VERSIONS["v2"],
        provenance=_create_provenance(v1_obj),
        submission=_convert_submission(v1_obj),
        experiments=_convert_experiments(v1_obj),
        sequences=_convert_sequences(v1_obj),
        features=_convert_features(v1_obj),
    )


def _qualifier_value_to_str(value: str | bool) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def _create_provenance(v1_obj: DdbjRecordV1) -> Provenance:
    """Create provenance metadata for v2."""
    return Provenance(
        dfast_version=v1_obj.COMMON_META.dfast_version,
    )


def _normalize_abbr(abbr: str) -> str:
    return re.sub(r"[.\-\s]", "", abbr).lower()


def _abbr_candidates_from_fullname(fullname: str) -> set[str]:
    name = fullname.strip()
    candidates: set[str] = set()

    def _add_candidate(last: str, initials: str) -> None:
        # Example: fullname="John A. Doe" -> last="Doe", initials="JA"
        if initials:
            candidates.add(f"{last},{initials}.")  # "Doe,JA."
            candidates.add(f"{last},{initials}")  # "Doe,JA"
            candidates.add(f"{last},{initials[0]}.")  # "Doe,J."
            candidates.add(f"{last},{initials[0]}")  # "Doe,J"
            candidates.add(f"{last},{'.'.join(list(initials))}.")  # "Doe,J.A."
            candidates.add(f"{last},{'.'.join(list(initials))}")  # "Doe,J.A"
        candidates.add(f"{last},")  # "Doe,"
        candidates.add(f"{last}")  # "Doe"

    # has Comma: "Last, First Middle"
    if "," in name:  # e.g., "Doe, John A."
        last, rest = [x.strip() for x in name.split(",", 1)]  # ["Doe", "John A."]
        rest_parts = [p for p in re.split(r"\s+", rest) if p]  # ["John", "A."]
        initials = "".join([p[0] for p in rest_parts if p])  # "JA"
        _add_candidate(last, initials)
    else:  # no Comma: "First Middle Last"
        parts = [p for p in re.split(r"\s+", name) if p]
        if len(parts) == 1:
            candidates.add(parts[0])
        else:
            first, last = parts[0], parts[-1]
            mids = parts[1:-1]
            initials = first[0] + "".join([m[0] for m in mids if m])  # "JA"
            _add_candidate(last, initials)

            # for asian names, e.g., "Yamada Taro" -> Last=Yamada, First=Taro
            last, first = parts[0], parts[-1]
            mids = parts[1:-1]
            initials = first[0] + "".join([m[0] for m in mids if m])
            _add_candidate(last, initials)

    return {_normalize_abbr(c) for c in candidates if c}


def _convert_submission(v1_obj: DdbjRecordV1) -> Submission:
    # === submitters ===
    submitters: list[Person] = []
    institution = Organization(
        name=v1_obj.COMMON.SUBMITTER.institute,
        url=v1_obj.COMMON.SUBMITTER.url,
        department=v1_obj.COMMON.SUBMITTER.department,
        type="institution",
        address=Address(
            country=v1_obj.COMMON.SUBMITTER.country,
            state=v1_obj.COMMON.SUBMITTER.state,
            city=v1_obj.COMMON.SUBMITTER.city,
            street=v1_obj.COMMON.SUBMITTER.street,
            postal_code=v1_obj.COMMON.SUBMITTER.zip,
        ),
    )

    contact_index: int | None = None
    if v1_obj.COMMON.SUBMITTER.contact:
        contact_candidates = _abbr_candidates_from_fullname(v1_obj.COMMON.SUBMITTER.contact)
        for i, ab_name in enumerate(v1_obj.COMMON.SUBMITTER.ab_name):
            if _normalize_abbr(ab_name) in contact_candidates:
                contact_index = i
                break

    for i, ab_name in enumerate(v1_obj.COMMON.SUBMITTER.ab_name):
        person = Person(abbreviation=ab_name)
        if contact_index is not None and i == contact_index:
            person.name = v1_obj.COMMON.SUBMITTER.contact
            person.email = v1_obj.COMMON.SUBMITTER.email
            person.organization = [institution]
            if v1_obj.COMMON.SUBMITTER.consrtm:
                person.organization.append(Organization(name=v1_obj.COMMON.SUBMITTER.consrtm, type="consortium"))
        submitters.append(person)

    if contact_index is None:
        if v1_obj.COMMON.SUBMITTER.contact:
            warnings.warn(
                f"contact '{v1_obj.COMMON.SUBMITTER.contact}' did not match any ab_name; "
                "adding as separate Person with abbreviation=None",
                UserWarning,
                stacklevel=2,
            )
        person = Person(abbreviation=None)
        person.name = v1_obj.COMMON.SUBMITTER.contact
        person.email = v1_obj.COMMON.SUBMITTER.email
        person.organization = [institution]
        if v1_obj.COMMON.SUBMITTER.consrtm:
            person.organization.append(Organization(name=v1_obj.COMMON.SUBMITTER.consrtm, type="consortium"))
        submitters.append(person)

    # === db_xrefs ===
    db_xrefs: list[Xref] = []
    if v1_obj.COMMON.DBLINK:
        if v1_obj.COMMON.DBLINK.project:
            db_xrefs.append(Xref(db="bioproject", id=v1_obj.COMMON.DBLINK.project))
        if v1_obj.COMMON.DBLINK.biosample:
            db_xrefs.append(Xref(db="biosample", id=v1_obj.COMMON.DBLINK.biosample))
        db_xrefs.extend(
            Xref(db="insdc.sra", id=sra_id) for sra_id in v1_obj.COMMON.DBLINK.sequence_read_archive or [] if sra_id
        )

    # === references ===
    references: list[Reference] = [
        Reference(
            title=ref.title,
            authors=[Person(abbreviation=ab_name) for ab_name in ref.ab_name],
            status="-".join(ref.status.lower().split(" ")),
            year=ref.year,
        )
        for ref in v1_obj.COMMON.REFERENCE
    ]

    # === comments ===
    comments: list[list[str]] = [comment.line for comment in v1_obj.COMMON.COMMENT]

    return Submission(
        submitters=submitters,
        db_xrefs=db_xrefs,
        references=references,
        comments=comments,
        trad_submission_category=v1_obj.COMMON.trad_submission_category,
        division=v1_obj.COMMON_META.division,
        locus_tag_prefix=v1_obj.COMMON_META.locus_tag_prefix,
        seq_prefix=v1_obj.COMMON_META.seq_prefix,
        hold_date=v1_obj.COMMON.DATE.hold_date if v1_obj.COMMON.DATE else None,
    )


def _convert_experiments(v1_obj: DdbjRecordV1) -> list[Experiment]:
    experiment = Experiment(
        id="st_comment_experiment",
        platform=Platform(platform_type=v1_obj.COMMON.ST_COMMENT.sequencing_technology),
        experiment_attributes={
            "tagset_id": v1_obj.COMMON.ST_COMMENT.tagset_id,
            "assembly_method": v1_obj.COMMON.ST_COMMENT.assembly_method,
        },
    )
    if v1_obj.COMMON.ST_COMMENT.coverage:
        experiment.experiment_attributes["coverage"] = v1_obj.COMMON.ST_COMMENT.coverage
    if v1_obj.COMMON.ST_COMMENT.genome_coverage:
        experiment.experiment_attributes["genome_coverage"] = v1_obj.COMMON.ST_COMMENT.genome_coverage

    return [experiment]


def _convert_sequences(v1_obj: DdbjRecordV1) -> Sequences:
    common_source = Source(
        organism=v1_obj.COMMON_SOURCE.organism, mol_type=v1_obj.COMMON_SOURCE.mol_type, qualifiers={}
    )
    value_from_cs: str | list[str]  # if key is 'note', value is List[str]
    for key, value_from_cs in v1_obj.COMMON_SOURCE.model_dump().items():
        if key in ("organism", "mol_type"):
            continue
        if value_from_cs is not None:
            arr_value = value_from_cs if isinstance(value_from_cs, list) else [value_from_cs]
            common_source.qualifiers[key] = [Qualifier(value=_qualifier_value_to_str(v)) for v in arr_value]

    entries: list[Entry] = []
    for entry in v1_obj.ENTRIES:
        # The source feature can be multiple in one entry.
        v1_source_features: list[FeatureV1] = []
        raw_comments: list[list[str]] = []
        for feature in entry.features:
            if feature.type == "source":
                v1_source_features.append(feature)
            if feature.type == "COMMENT":
                raw_comments.append([str(v) for v in feature.qualifiers.get("line", [])])

        # Remove empty lists from comments
        comments: list[list[str]] | None = [c for c in raw_comments if c] or None

        v2_source_features: list[SourceFeature] = []
        for v1_sf in v1_source_features:
            v2_sf_source = None  # source for each source feature
            if "organism" in v1_sf.qualifiers and "mol_type" in v1_sf.qualifiers:
                v2_sf_source = Source(
                    organism=v1_sf.qualifiers["organism"][0], mol_type=v1_sf.qualifiers["mol_type"][0], qualifiers={}
                )
                for key, value in v1_sf.qualifiers.items():
                    if key in ("organism", "mol_type", "ff_definition"):
                        continue
                    v2_sf_source.qualifiers[key] = [Qualifier(value=_qualifier_value_to_str(v)) for v in value]
            v2_sf_definition = None  # definition for each source feature
            if "ff_definition" in v1_sf.qualifiers:
                v2_sf_definition = v1_sf.qualifiers["ff_definition"]

            v2_sf = SourceFeature(
                id=v1_sf.id,
                location=v1_sf.location,
                source=v2_sf_source,
                definition=v2_sf_definition,
            )
            v2_source_features.append(v2_sf)

        entries.append(
            Entry(
                id=entry.id,
                name=entry.name,
                type=entry.type,
                topology=entry.topology,
                sequence=entry.sequence,
                source_features=v2_source_features,
                comments=comments,
            )
        )

    return Sequences(
        common_source=common_source,
        entries=entries,
    )


def _convert_features(v1_obj: DdbjRecordV1) -> list[Feature]:
    features: list[Feature] = []

    for entry in v1_obj.ENTRIES:
        for feature in entry.features:
            if feature.type in ("source", "COMMENT"):
                continue
            features.append(
                Feature(
                    id=feature.id,
                    type=feature.type,
                    location=feature.location,
                    sequence_id=entry.id,
                    qualifiers={
                        key: [Qualifier(value=_qualifier_value_to_str(v)) for v in value]
                        for key, value in feature.qualifiers.items()
                    },
                    locus_tag_id=feature.locus_tag_id,
                )
            )

    return features
