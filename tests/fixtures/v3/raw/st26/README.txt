After validation of the following files, the results should be as follows:
- Error_The_Applicant_File_Reference_number_is_missing: red banner is displayed. The verification report indicates that there are two warnings: one for the earliest priority application being missing and one for the applicant file reference being missing.
- Error-Mandatory_qualifier_MOL_TYPE_for_the_feature_SOURCE_is_missing: red banner is displayed. The verification report indicates that the mandatory qualifier MOL_TYPE is missing.
- Error-Missing_Non_English_Qualifier_Value: red banner displayed. The verification report indicates that a non English free text language code has been entered but there are no qualifiers with a non English free text value.
- Valid_DNA_AA_project: blue banner indicating that the sequence listing is valid
- Valid-Exemplary_DNA_and_AA: blue banner indicating that the sequence listing is valid

After import of the following files, the results should be as follows:
- Error_The_Applicant_File_Reference_number_is_missing: blue banner is displayed. No messages provided in import report. 
- Error-Mandatory_qualifier_MOL_TYPE_for_the_feature_SOURCE_is_missing: blue banner is displayed. No messages provided in import report. 
- Error-Missing_Non_English_Qualifier_Value: blue banner is displayed. Change data report indicates that for SEQ ID 2 a qID was generated for the qualifier. 
- Valid_DNA_AA_project: blue banner indicating that import was successful. No messages provided in import report.
- Valid-Exemplary_DNA_and_AA: blue banner indicating that import was successful. No messages provided in import report.
