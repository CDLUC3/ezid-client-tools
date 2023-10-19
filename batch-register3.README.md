# Batch Register Identifiers

The **batch-register** tool registers identifiers, reads an input CSV file containing identifier metadata (one row per identifier), transforms the metadata into EZID metadata based on a configuration file of mappings, creates or mints identifiers (or updates existing ones), and finally outputs a CSV file containing the created, minted, or updated identifiers along with additional information.

All input and output files are assumed to be UTF-8 encoded.

## Usage

```plaintext
batch-register [options] operation mappings input.csv
```

- `operation`: Can be `create`, `mint`, or `update`.
- `mappings`: Configuration file for mappings (explained below).
- `input.csv`: Input metadata in CSV format.

### Options

- `-c CREDENTIALS`: Specify credentials for EZID. This can be either `username:password`, `username` (password will be prompted for), or `sessionid=...` (as obtained using the EZID client tool).
- `-o COLUMNS`: Comma-separated list of columns to output (default is `_n,_id,_error`).
- `-p`: Preview mode. This option doesn't register identifiers but instead writes transformed metadata to the standard output.
- `-r`: Remove any mapping to `_id`. This is useful when temporarily minting.
- `-s SHOULDER`: The shoulder to mint under, e.g., `ark:/99999/fk4`.
- `-t`: Tab mode. If this option is enabled, the input metadata is tab-separated (multiline values and tab characters in values are not supported).

## Mappings

The mappings file defines how input CSV columns are mapped to EZID metadata elements. Each line in the file should have the following form:

```plaintext
destination = expression
```

- The `destination` in a mapping can be an EZID element name (e.g., `erc.who`, `dc.title`, `_target`, etc.) or an XPath absolute path of a DataCite metadata schema element or attribute (e.g., `/resource/titles/title` for an element, `/resource/titles/title@titleType` for an attribute). If any XPaths are present, a DataCite XML record is constructed and assigned as the value of the EZID element 'datacite'.
- A special destination element, `_id`, is used to identify the identifier to create or update.
- The `expression` in a mapping is a string in which column values are interpolated. Columns are referenced using 1-based indexing and may be referred to using the syntaxes `$n` or `${n}`. Use `$$` for a literal dollar sign.

## Example Mapping

For example, if you have an input CSV file with six columns:

```plaintext
title,author,orcid,publisher_name,publisher_place,url
```

A complete mapping to mint DOI identifiers would be:

```plaintext
_profile = datacite
/resource/titles/title = $1
/resource/creators/creator/creatorName = $2
/resource/creators/creator/nameIdentifier = $3
/resource/creators/creator/nameIdentifier@nameIdentifierScheme = ORCID
/resource/publisher = $4 ($5)
/resource/publicationYear = 2018
/resource/resourceType@resourceTypeGeneral = Dataset
_target = $6
```

This mapping defines how columns in your input CSV correspond to the required metadata elements for EZID registration.

## Limitations

- It's not possible to update just a portion of existing DataCite XML records. The order of mappings determines the ordering of XML elements.
- When mapping to both a DataCite metadata schema element and an attribute of that element, the mapping to the element must come first in the mappings file.
- Multiple mappings to EZID metadata elements and DataCite metadata schema attributes are not supported; the last mapping overwrites any previous mappings. However, for DataCite metadata schema elements, multiple mappings create multiple XML elements.

## User-Supplied Functions

User-supplied functions provide more flexibility in mapping. A user-supplied function can return:

1. A string value.
2. A tuple (relpath, value), where `relpath` is an XPath relative path of a DataCite metadata schema element or attribute, and `value` is any valid return from a user-supplied function (string, tuple, or list).
3. A list of zero or more tuples.

User-supplied functions are required in certain cases to create the necessary hierarchical DataCite XML structure.

## Output

The output, written to standard output, is a CSV file. The columns in the output can be configured using the `-o` option. Additional columns like `_n`, the record number in the input file, `_id`, the identifier created, minted, or updated, and `_error`, the error message in case of registration failure, can also be specified.

The default output is `_n,_id,_error`.

### Preview Mode

The `-p` (preview mode) option allows you to examine the metadata that will be submitted. This can be helpful for confirming that the transformation is operating as expected.

## Test Shoulders

Before running a batch create or mint job, you may want to mint using a test shoulder to ensure that all metadata is well-formed and accepted. The test shoulders are `ark:/99999/fk4` for ARK identifiers and `doi:10.5072/FK2` for DOI identifiers.