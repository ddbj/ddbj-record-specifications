"""v2 の record を v3 に変換する。

v2 の項目は、次のものを除いて v3 に置き場がある。置き場の無いものは落とし、`UserWarning` を出す。

- `submission.datatype` (MSS の DATATYPE)。v3 では `provenance.submission_category` から決めるので、
  `trad_submission_category` と同じ値なら黙って落とし、違う値のときだけ warning を出す
- `references[].consortiums[]` の名前以外。v3 の `Publication.consortiums` は名前の list
- ST_COMMENT を表す experiment (`id` が "st_comment_experiment") の `title` と `design`、`platform.instrument_model`
- `references[].year` のうち、`date_published` と食い違うもの (v3 の `date` は 1 つ)

v2 の `Qualifier.value` の "true" は、値の無い qualifier (`/pseudo` など) を表す。v3 では value を省く。
"""

from __future__ import annotations

import warnings
from typing import Any, TypeVar

from pydantic import BaseModel

from ddbj_record.schema.v2 import DdbjRecord as DdbjRecordV2
from ddbj_record.schema.v2 import Entry as EntryV2
from ddbj_record.schema.v2 import Experiment as ExperimentV2
from ddbj_record.schema.v2 import Feature as FeatureV2
from ddbj_record.schema.v2 import Organization as OrganizationV2
from ddbj_record.schema.v2 import Person as PersonV2
from ddbj_record.schema.v2 import Qualifier as QualifierV2
from ddbj_record.schema.v2 import Reference as ReferenceV2
from ddbj_record.schema.v2 import Source as SourceV2
from ddbj_record.schema.v2 import SourceFeature as SourceFeatureV2
from ddbj_record.schema.v2 import Submission as SubmissionV2
from ddbj_record.schema.v2 import Xref as XrefV2
from ddbj_record.schema.v3 import (
    Address,
    Attribute,
    Entry,
    Experiment,
    Feature,
    LibraryDescriptor,
    LocusTagPrefix,
    Organism,
    Organization,
    Person,
    Platform,
    Project,
    Provenance,
    Publication,
    Qualifier,
    Relation,
    RelationTarget,
    Sequences,
    Source,
    SourceFeature,
    StructuredComment,
    Submission,
    TargetedLocus,
)
from ddbj_record.schema.v3 import DdbjRecord as DdbjRecordV3

# v2 は Trad の ST_COMMENT を、この id を持つ experiment に置いている。
ST_COMMENT_EXPERIMENT_ID = "st_comment_experiment"

# ST_COMMENT の項目名。v2 の experiment_attributes のキーから、MSS の書き方 (v3 の fields のキー) に戻す。
_ST_COMMENT_FIELD_NAMES = {
    "assembly_method": "Assembly Method",
    "genome_coverage": "Genome Coverage",
    "coverage": "Coverage",
}

_T = TypeVar("_T")
_M = TypeVar("_M", bound=BaseModel)


def _warn_data_loss(msg: str) -> None:
    warnings.warn(msg, UserWarning, stacklevel=3)


def _list_or_none(items: list[_T]) -> list[_T] | None:
    """v3 は全て optional なので、空の list は省く。"""
    return items or None


def _or_none(model: _M) -> _M | None:
    """値を 1 つも持たないモデルは省く。"""
    return model if model.model_dump(exclude_none=True) else None


def v2_to_v3(v2_obj: DdbjRecordV2) -> DdbjRecordV3:
    structured_comments, experiments = _convert_experiments(v2_obj.experiments)
    return DdbjRecordV3(
        schema_version="v3",
        provenance=_convert_provenance(v2_obj),
        submission=_convert_submission(v2_obj.submission),
        projects=_convert_projects(v2_obj.submission),
        experiments=experiments,
        sequences=_convert_sequences(v2_obj, structured_comments),
        features=_convert_features(v2_obj.features),
        relations=_convert_relations(v2_obj.submission.db_xrefs),
    )


# === provenance ===


def _convert_provenance(v2_obj: DdbjRecordV2) -> Provenance | None:
    # v2 の Provenance も型に無いキー (dfast_version など) を持つので、そのまま v3 に移す。
    data: dict[str, Any] = dict(v2_obj.provenance.model_extra or {})
    data["source_format"] = v2_obj.provenance.source_format
    data["submission_category"] = v2_obj.submission.trad_submission_category
    return _or_none(Provenance.model_validate(data))


# === submission ===


def _convert_address(organization: OrganizationV2) -> Address | None:
    if organization.address is None:
        return None
    return Address(
        country=organization.address.country,
        state=organization.address.state,
        city=organization.address.city,
        street=organization.address.street,
        postal_code=organization.address.postal_code,
    )


def _convert_organization(organization: OrganizationV2) -> Organization:
    return Organization(
        name=organization.name,
        abbreviation=organization.abbreviation,
        url=organization.url,
        role=organization.role,
        type=organization.type,
        department=organization.department,
        address=_convert_address(organization),
        ror_id=organization.ror_id,
    )


def _convert_person(person: PersonV2, role: str | None = None) -> Person:
    return Person(
        name=person.name,
        abbreviation=person.abbreviation,
        email=person.email,
        orcid=person.orcid,
        role=role,
        organizations=_list_or_none([_convert_organization(o) for o in person.organization or []]),
    )


def _join_comment_lines(comments: list[list[str]]) -> list[str] | None:
    """v2 の 1 つのコメント (行の list) を、v3 の 1 つの文字列にする。行の無いコメントは省く。"""
    return _list_or_none(["\n".join(lines) for lines in comments if lines])


def _convert_submission(submission: SubmissionV2) -> Submission | None:
    # v2 も v3 も先頭の人が連絡先。v3 の Trad の record に合わせて role も書く。
    submitters = [
        _convert_person(person, role="contact" if i == 0 else "submitter")
        for i, person in enumerate(submission.submitters)
    ]
    return _or_none(
        Submission(
            submitters=_list_or_none(submitters),
            hold_date=submission.hold_date,
            comments=_join_comment_lines(submission.comments),
        )
    )


# === projects ===


def _publication_date(reference: ReferenceV2) -> str | None:
    """v3 の date は 1 つ。date_published があればそれを、無ければ year を使う。"""
    if reference.date_published:
        if reference.year and not reference.date_published.startswith(reference.year):
            _warn_data_loss(
                f"reference year '{reference.year}' differs from date_published '{reference.date_published}'; "
                "v3 keeps date_published only"
            )
        return reference.date_published
    return reference.year or None


def _convert_publication(reference: ReferenceV2) -> Publication:
    for consortium in reference.consortiums or []:
        if consortium.model_dump(exclude_none=True, exclude={"name"}):
            _warn_data_loss(
                f"reference consortium '{consortium.name}': v3 keeps only the name of a consortium; "
                "other organization fields are dropped"
            )
    return Publication(
        title=reference.title,
        pubmed_id=reference.pubmed_id,
        doi=reference.doi,
        status=reference.status,
        date=_publication_date(reference),
        journal=reference.journal,
        volume=reference.volume,
        issue=reference.issue,
        pages_from=reference.start_page,
        pages_to=reference.end_page,
        url=reference.url,
        authors=_list_or_none([_convert_person(author) for author in reference.authors]),
        consortiums=_list_or_none([consortium.name for consortium in reference.consortiums or []]),
    )


def _convert_projects(submission: SubmissionV2) -> list[Project] | None:
    """references と locus_tag_prefix を、accession を持たない 1 つの project に置く。どちらも無ければ省く。"""
    locus_tag_prefix: list[LocusTagPrefix] | None = None
    if submission.locus_tag_prefix is not None:
        locus_tag_prefix = [LocusTagPrefix(prefix=submission.locus_tag_prefix)]
    project = _or_none(
        Project(
            publications=_list_or_none([_convert_publication(reference) for reference in submission.references]),
            locus_tag_prefix=locus_tag_prefix,
        )
    )
    return [project] if project is not None else None


# === relations ===


def _convert_relations(db_xrefs: list[XrefV2]) -> list[Relation] | None:
    # source を省き、record 全体から外部 DB への参照にする。
    return _list_or_none([Relation(type="xref", target=RelationTarget(db=xref.db, id=xref.id)) for xref in db_xrefs])


# === experiments ===


def _convert_structured_comment(experiment: ExperimentV2) -> StructuredComment:
    if experiment.title is not None:
        _warn_data_loss(f"title of {ST_COMMENT_EXPERIMENT_ID} has no place in a structured comment; dropped")
    if experiment.design is not None:
        _warn_data_loss(f"design of {ST_COMMENT_EXPERIMENT_ID} has no place in a structured comment; dropped")

    tagset_id: str | None = None
    fields: dict[str, str] = {}
    for key, value in experiment.experiment_attributes.items():
        if key == "tagset_id":
            tagset_id = value
        else:
            fields[_ST_COMMENT_FIELD_NAMES.get(key, key)] = value
    if experiment.platform is not None:
        if experiment.platform.platform_type is not None:
            fields["Sequencing Technology"] = experiment.platform.platform_type
        if experiment.platform.instrument_model is not None:
            _warn_data_loss(
                f"instrument_model of {ST_COMMENT_EXPERIMENT_ID} has no place in a structured comment; dropped"
            )
    return StructuredComment(tagset_id=tagset_id, fields=fields or None)


def _convert_attributes(experiment_attributes: dict[str, str]) -> list[Attribute] | None:
    attributes: list[Attribute] = []
    for name, value in experiment_attributes.items():
        if not name.strip():
            _warn_data_loss(f"experiment attribute with a blank name (value '{value}') is dropped")
            continue
        attributes.append(Attribute(name=name, value=value))
    return _list_or_none(attributes)


def _convert_experiment(experiment: ExperimentV2) -> Experiment:
    description: str | None = None
    library: LibraryDescriptor | None = None
    targeted_loci: list[TargetedLocus] | None = None
    if experiment.design is not None:
        design = experiment.design
        layout = design.library_layout
        description = design.design_description
        library = _or_none(
            LibraryDescriptor(
                name=design.library_name,
                strategy=design.library_strategy,
                source=design.library_source,
                selection=design.library_selection,
                # v2 は "SINGLE" / "PAIRED"、v3 は "single" / "paired"。
                layout=layout.layout_type.lower() if layout is not None else None,
                nominal_length=layout.nominal_length if layout is not None else None,
                nominal_sdev=layout.nominal_sdev if layout is not None else None,
                construction_protocol=design.library_construction_protocol,
                pooling_strategy=design.pooling_strategy,
            )
        )
        targeted_loci = _list_or_none(
            [
                TargetedLocus(name=locus.locus_name, description=locus.description)
                for locus in design.targeted_loci or []
            ]
        )

    platform: Platform | None = None
    if experiment.platform is not None:
        platform = _or_none(
            Platform(type=experiment.platform.platform_type, instrument_model=experiment.platform.instrument_model)
        )

    return Experiment(
        alias=experiment.id,
        title=experiment.title,
        description=description,
        library=library,
        platform=platform,
        targeted_loci=targeted_loci,
        attributes=_convert_attributes(experiment.experiment_attributes),
    )


def _convert_experiments(
    experiments: list[ExperimentV2],
) -> tuple[list[StructuredComment] | None, list[Experiment] | None]:
    """ST_COMMENT の experiment は sequences.structured_comments に、それ以外は experiments に分ける。"""
    structured_comments: list[StructuredComment] = []
    others: list[Experiment] = []
    for experiment in experiments:
        if experiment.id == ST_COMMENT_EXPERIMENT_ID:
            structured_comments.append(_convert_structured_comment(experiment))
        else:
            others.append(_convert_experiment(experiment))
    return _list_or_none(structured_comments), _list_or_none(others)


# === sequences ===


def _convert_qualifier(qualifier: QualifierV2) -> Qualifier:
    # v2 は値の無い qualifier を "true" で表す。v3 は value を省く。
    return Qualifier(alias=qualifier.id, value=None if qualifier.value == "true" else qualifier.value)


def _convert_qualifiers(qualifiers: dict[str, list[QualifierV2]]) -> dict[str, list[Qualifier]] | None:
    if not qualifiers:
        return None
    return {name: [_convert_qualifier(qualifier) for qualifier in values] for name, values in qualifiers.items()}


def _convert_source(source: SourceV2) -> Source:
    return Source(
        organism=Organism(name=source.organism),
        mol_type=source.mol_type,
        qualifiers=_convert_qualifiers(source.qualifiers),
    )


def _convert_source_feature(source_feature: SourceFeatureV2) -> SourceFeature:
    return SourceFeature(
        alias=source_feature.id,
        location=source_feature.location,
        source=_convert_source(source_feature.source) if source_feature.source is not None else None,
        definition=source_feature.definition or None,
    )


def _convert_entry(entry: EntryV2, division: str | None) -> Entry:
    return Entry(
        alias=entry.id,
        name=entry.name,
        type=entry.type,
        topology=entry.topology,
        # v2 は record に 1 つの division を、v3 は entry ごとに持つ。
        division=division,
        sequence=entry.sequence,
        comments=_join_comment_lines(entry.comments or []),
        source_features=_list_or_none([_convert_source_feature(sf) for sf in entry.source_features]),
    )


def _convert_sequences(v2_obj: DdbjRecordV2, structured_comments: list[StructuredComment] | None) -> Sequences:
    submission = v2_obj.submission
    if submission.datatype is not None and submission.datatype != submission.trad_submission_category:
        _warn_data_loss(
            f"submission.datatype '{submission.datatype}' has no place in v3 and differs from "
            f"trad_submission_category '{submission.trad_submission_category}'; dropped"
        )
    return Sequences(
        seq_prefix=submission.seq_prefix,
        common_source=_convert_source(v2_obj.sequences.common_source),
        entries=_list_or_none([_convert_entry(entry, submission.division) for entry in v2_obj.sequences.entries]),
        structured_comments=structured_comments,
        keywords=submission.keywords or None,
    )


# === features ===


def _convert_features(features: list[FeatureV2]) -> list[Feature] | None:
    return _list_or_none(
        [
            Feature(
                alias=feature.id,
                type=feature.type,
                location=feature.location,
                sequence_id=feature.sequence_id,
                qualifiers=_convert_qualifiers(feature.qualifiers),
                locus_tag_id=feature.locus_tag_id,
            )
            for feature in features
        ]
    )
