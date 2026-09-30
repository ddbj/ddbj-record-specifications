"""DDBJ Record v4: v3 の record を、1 つの zip(パッケージ)で渡す形。

record の中身は v3 と同じで、違いは entry が配列を持たず、配列の長さと digest を持つことだけ。
配列はパッケージの FASTA に、数に上限の無いオブジェクトの list は JSON Lines に置く
(docs/v4-schema.md、ddbj_record/package.py)。

変わるモデル(Entry と、それを含む Sequences、DdbjRecord)はここで定義し、ほかは v3 のものを使う。
v3 のクラスを継承しないのは、v4 の record を v3 の record として受け付けさせないため。
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ddbj_record.schema import v3


class Entry(BaseModel):
    """配列の一つ。配列そのものはパッケージの FASTA にあり、alias で引く。

    sequence_digest は GA4GH refget の sha512t24u に "SQ." を付けたもの。
    """

    # version を含む ("AB123456.1")。alias は登録者が付けた名前で、FASTA の見出しでもある。
    accession: str | None = Field(None, examples=["AB123456.1"])
    alias: str | None = Field(None, examples=["contig_001"])
    name: str | None = None
    type: str | None = Field(None, examples=["chromosome"])
    topology: str | None = Field(None, examples=["circular"])
    # GenBank の division。
    division: str | None = Field(None, examples=["BCT"])
    length: int | None = Field(None, ge=0, examples=[2277985])
    sequence_digest: str | None = Field(
        None, pattern=r"^SQ\.[A-Za-z0-9_-]{32}$", examples=["SQ.aKF498dAxcJAqme6QYQ7EZ07-fiw8Kw2"]
    )
    comments: list[str] | None = None
    source_features: list[v3.SourceFeature] | None = None

    model_config = ConfigDict(extra="forbid")


class Sequences(BaseModel):
    seq_prefix: str | None = Field(None, examples=["contig"])
    # 全ての entry の source feature に共通する値。Sample.organism とは別に持つ。
    common_source: v3.Source | None = None
    entries: list[Entry] | None = None
    structured_comments: list[v3.StructuredComment] | None = None
    attributes: list[v3.Attribute] | None = None

    model_config = ConfigDict(extra="forbid")


class DdbjRecord(BaseModel):
    schema_version: str | None = Field(None, examples=["v4"])
    provenance: v3.Provenance | None = None
    submission: v3.Submission | None = None
    projects: list[v3.Project] | None = None
    samples: list[v3.Sample] | None = None
    experiments: list[v3.Experiment] | None = None
    runs: list[v3.Run] | None = None
    analyses: list[v3.Analysis] | None = None
    sequences: Sequences | None = None
    features: list[v3.Feature] | None = None
    assembly: v3.Assembly | None = None
    datasets: list[v3.Dataset] | None = None
    relations: list[v3.Relation] | None = None
    access_control: v3.AccessControl | None = None
    array_design: v3.ArrayDesign | None = None

    model_config = ConfigDict(extra="forbid")
