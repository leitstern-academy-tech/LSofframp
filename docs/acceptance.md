# Acceptance criteria

Each requirement from `docs/requirements.md` is accepted when the listed tests pass
(`python -m pytest -q`). Test names refer to files in `tests/`.

| ID | Accepted when | Tests |
| --- | --- | --- |
| R-01 | No network code exists in the package; reviewed by reading the imports. | Manual review (no automated test yet) |
| R-02 | ZIP and directory scans find the same files with the same hashes; folders are kept. | `test_zip_entries_are_hashed_and_sorted`, `test_zip_directory_entries_are_kept_as_folders`, `test_directory_scan_matches_zip_scan` |
| R-03 | Each kind of unsafe entry is reported and skipped; other entries survive. | `test_unsafe_zip_paths_are_skipped_not_fatal`, `test_symlink_entries_are_skipped`, `test_encrypted_entries_are_reported`, `test_crc_corruption_is_reported_and_other_entries_survive`, `test_duplicate_paths_keep_the_first_entry`, `test_case_collisions_are_reported_but_both_kept`, `test_directory_symlinks_are_not_followed`, `test_non_zip_file_raises_package_error`, `test_missing_path_raises_package_error`, `test_unsafe_paths_are_rejected` |
| R-04 | Every limit stops or skips as described and is reported. | `test_entry_size_limit`, `test_total_size_limit_stops_the_scan`, `test_entry_count_limit`, `test_directory_entry_limit`, `test_extreme_compression_ratio_is_not_read`, `test_small_highly_compressible_entries_are_fine` |
| R-05 | Same input gives identical output regardless of input order. | `test_same_input_gives_identical_manifest`, `test_output_does_not_depend_on_input_order`, `test_same_input_gives_identical_evidence`, `test_digest_changes_when_content_changes`, `test_directory_digest_ignores_walk_order`, `test_directory_digest_is_stable_and_content_sensitive` |
| R-06 | URL secrets are removed and unknown fields (such as a mail subject) are refused. | `test_url_secrets_are_removed`, `test_external_reference_drops_query_and_rejects_empty_result`, `test_unknown_fields_are_rejected` |
| R-07 | Unknown and empty stay distinct in the file and in the rules. | `test_null_and_empty_sharing_stay_distinct`, `test_unknown_information_stays_unknown`, `test_sharing_unknown_is_not_the_same_as_nobody` |
| R-08 | The stored schema equals the schema generated from the models. | `test_schema_file_matches_models` |
| R-09 | The pack's manifest digest equals the SHA-256 of the written manifest file. | `test_build_evidence_binds_manifest_and_issues` |
| R-10 | The four states are produced as specified and the pack has no score field. | `test_pack_has_no_overall_score`, `test_read_complete_passes_without_issues`, `test_read_complete_fails_and_names_touched_objects`, `test_open_formats_fails_on_closed_formats_and_lists_them`, `test_open_formats_cannot_determine_for_unclassified_files`, `test_open_formats_passes_when_everything_is_open`, `test_open_formats_without_files_is_not_applicable`, `test_checksums_cannot_be_judged_when_package_declares_none`, `test_checksums_fail_on_missing_hash_or_mismatch`, `test_checksums_pass_when_declared_hashes_match`, `test_checksums_with_uncompared_declaration_stay_undetermined` |
| R-11 | A raising rule yields cannot_determine and the run continues. | `test_failing_rule_is_reported_not_raised` |
| R-12 | The checksum file matches, a changed file is detected, a missing checksum file is an error. | `test_write_load_roundtrip_with_checksum_file`, `test_changed_file_fails_verification`, `test_missing_checksum_file_is_an_error` |
| R-13 | Parts are combined; same-named parts are refused; repeated files and folders are handled. | `test_read_packages_combines_parts`, `test_read_packages_rejects_same_name_twice`, `test_repeated_file_across_parts_is_reported_once`, `test_repeated_folder_across_parts_is_merged_silently` |
| R-14 | The five commands run and print what the README shows. | Manual check (no automated test yet) |
| N-01 | Tests pass on Windows and on Linux (Python 3.13). | Manual runs on both systems |

## Known gaps

- The command line has no automated tests yet (R-14).
- R-01 is checked by reading the code, not by a test.
- The Evidence Pack has no JSON Schema file yet (P-07).
- Format detection is by file extension only; `test_describe_format_by_extension` and
  `test_describe_format_without_extension` cover the table, not file content.
