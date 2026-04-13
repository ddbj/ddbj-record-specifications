# CHANGELOG

Application version (Python パッケージ) のリリースごとに変更内容を記録する。
Specification version (スキーマ仕様) の変更も合わせて記載する。
バージョニングの方針は [README.md](./README.md#バージョニング) を参照。

## Unreleased

- Specification version を v1.0 / v2.0 として確定し、バージョニングルールを導入
- v2.3: 全 list/dict フィールドから default_factory を除去し required 化

## 0.1.0 ~ 0.1.5 (2025-08-18 ~ 2025-09-10)

Spec v1, v2 のスキーマ定義、validator、converter (v1<->v2)、Feature Table 定義 (実験的) を実装。
バージョニングルール導入前のため、詳細は git log を参照。
