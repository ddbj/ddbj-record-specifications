from ddbj_record.insdc import load_insdc_definition
from ddbj_record.insdc.models import InsdcDefinition


def test_load_insdc_definition_returns_valid_model() -> None:
    definition = load_insdc_definition()
    assert isinstance(definition, InsdcDefinition)


def test_load_insdc_definition_has_meta() -> None:
    definition = load_insdc_definition()
    assert definition.meta.insdc_version == "11.3"
    assert len(definition.meta.sources) > 0


def test_load_insdc_definition_has_features() -> None:
    definition = load_insdc_definition()
    assert len(definition.features) >= 43
    assert "CDS" in definition.features
    assert "source" in definition.features
    assert "assembly_gap" in definition.features
    assert "3'UTR" in definition.features
    assert "5'UTR" in definition.features


def test_load_insdc_definition_has_qualifiers() -> None:
    definition = load_insdc_definition()
    assert len(definition.qualifiers) >= 80
    assert "product" in definition.qualifiers
    assert "organism" in definition.qualifiers
    assert "mol_type" in definition.qualifiers
    assert "codon_start" in definition.qualifiers


def test_load_insdc_definition_has_cross_constraints() -> None:
    definition = load_insdc_definition()
    assert len(definition.cross_constraints) > 0


def test_qualifier_controlled_vocabulary_has_values() -> None:
    definition = load_insdc_definition()
    mol_type = definition.qualifiers["mol_type"]
    assert mol_type.value_format == "controlled_vocabulary"
    assert mol_type.controlled_vocabulary is not None
    assert "genomic DNA" in mol_type.controlled_vocabulary
    assert "mRNA" in mol_type.controlled_vocabulary


def test_qualifier_none_format_for_boolean() -> None:
    definition = load_insdc_definition()
    pseudo = definition.qualifiers["pseudo"]
    assert pseudo.value_format == "none"
    assert pseudo.deprecated is not None
    assert pseudo.deprecated.replacement == "pseudogene"


def test_feature_has_mandatory_and_optional_qualifiers() -> None:
    definition = load_insdc_definition()
    assembly_gap = definition.features["assembly_gap"]
    assert assembly_gap.qualifiers["estimated_length"] == "mandatory"
    assert assembly_gap.qualifiers["gap_type"] == "mandatory"
    assert assembly_gap.qualifiers["linkage_evidence"] == "optional"


def test_source_feature_has_mandatory_qualifiers() -> None:
    definition = load_insdc_definition()
    source = definition.features["source"]
    assert source.qualifiers["organism"] == "mandatory"
    assert source.qualifiers["mol_type"] == "mandatory"
    assert source.qualifiers["collection_date"] == "mandatory"
    assert source.qualifiers["geo_loc_name"] == "mandatory"


def test_cds_feature_has_expected_qualifiers() -> None:
    definition = load_insdc_definition()
    cds = definition.features["CDS"]
    assert "product" in cds.qualifiers
    assert "gene" in cds.qualifiers
    assert "codon_start" in cds.qualifiers
    assert "transl_table" in cds.qualifiers
    assert "pseudo" in cds.qualifiers
    assert "pseudogene" in cds.qualifiers


def test_deprecated_qualifier_has_message() -> None:
    definition = load_insdc_definition()
    country = definition.qualifiers["country"]
    assert country.deprecated is not None
    assert country.deprecated.replacement == "geo_loc_name"
    assert len(country.deprecated.message) > 0


def test_load_insdc_definition_is_cached() -> None:
    d1 = load_insdc_definition()
    d2 = load_insdc_definition()
    assert d1 is d2
