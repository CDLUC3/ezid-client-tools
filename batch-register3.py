#!/usr/bin/env python
import argparse
import base64
import csv
import getpass
import re
import sys
import urllib.request, urllib.parse, urllib.error
import xml.etree.ElementTree as ET

# Define a function to load mappings from a file and validate their format
def load_mappings(file):
    """
    Load mappings from a configuration file.

    Args:
        file (str): Path to the mappings configuration file.

    Returns:
        list: List of tuples (destination, expression).
    """
    mappings = []
    with open(file, 'r') as f:
        for line in f:
            parts = line.strip().split('=')
            assert len(parts) == 2, "Invalid syntax in mapping file"
            destination, expression = parts[0].strip(), parts[1].strip()
            if destination.startswith('/'):
                assert re.match(r'/resource(/\w+)+(@\w+)?$', destination), "Invalid XPath expression"
            else:
                assert re.match(r'[\w.]+$', destination), "Invalid element name"
            mappings.append((destination, expression))
    return mappings

# Define a function to parse the output columns configuration
def parse_output_columns(columns, mappings):
    """
    Parse and validate the output columns configuration.

    Args:
        columns (str): Comma-separated list of columns to output.
        mappings (list): List of mapping tuples.

    Returns:
        list: List of columns to output.
    """
    output_columns = ["_n", "_id", "_error"]
    elements = [d for d, e in mappings if not d.startswith("/")]
    for column in columns.split(','):
        if column == "_n" or column == "_id" or column == "_error":
            output_columns.append(column)
        elif column.isnumeric():
            column_index = int(column)
            assert 1 <= column_index <= len(mappings), "Invalid input column reference"
            output_columns.append(column_index - 1)
        else:
            assert column in elements, f"No such output element: {column}"
    return output_columns

# Define a function to interpolate expressions with row values
def interpolate(expression, row):
    """
    Interpolate expressions with row values.

    Args:
        expression (str): Expression to interpolate.
        row (list): List of column values.

    Returns:
        str: Interpolated string.
    """
    def replace_match(match):
        match_str = match.group(0)
        if match_str == "$$":
            return "$"
        if match_str.startswith("${"):
            parts = match_str[2:-1].split(':')
            if len(parts) > 1:
                column_indexes = [int(index) for index in parts[0].split(',')]
                function_name = parts[1]
                function_args = [row[index - 1] for index in column_indexes]
                try:
                    import functions
                    result = getattr(functions, function_name)(*function_args)
                    if isinstance(result, str):
                        return result
                    elif match_str == expression:
                        return result
                except Exception as e:
                    assert False, f"Error calling user-supplied function {function_name}: {str(e)}"
            else:
                return row[int(parts[0]) - 1]
        else:
            return row[int(match_str[1:]) - 1]

    interpolated_expression = re.sub(r'\$[0-9]+|\$\{[0-9]+\}|\$\{[0-9]+:[a-zA-Z_]+\}|\$\$', replace_match, expression)
    return interpolated_expression.strip()

# Define a function to set DataCite values in XML nodes
def set_datacite_value(node, path, value):
    """
    Set DataCite values in XML nodes.

    Args:
        node (ElementTree.Element): XML node.
        path (str): Absolute or relative XPath to set the value.
        value (str or complex object): Value to set.

    Returns:
        ElementTree.Element: The modified XML node.
    """
    def q(tag):
        return "{http://datacite.org/schema/kernel-4}" + tag

    if isinstance(value, tuple):
        value = [value]
    if isinstance(value, list):
        assert all(isinstance(v, tuple) and len(v) == 2 and isinstance(v[0], str) for v in value), "Invalid return value from user-supplied function: Malformed list or tuple"
        assert all(re.match(r'(\w+|[.])(/(\w+|[.]))*(@\w+)?$', v[0]) for v in value), "Invalid return value from user-supplied function: Invalid relative XPath expression"
    elif isinstance(value, str):
        value = value.strip()
        if value == "":
            return node
    else:
        assert False, "Invalid return value from user-supplied function"

    parts = path.split("@")
    attribute = parts[-1] if len(parts) > 1 else None
    path_elements = parts[0].split("/")

    if node is None:
        node = ET.Element(q("resource"))
        node.attrib["{http://www.w3.org/2001/XMLSchema-instance}schemaLocation"] = "http://datacite.org/schema/kernel-4 http://schema.datacite.org/meta/kernel-4/metadata.xsd"
        identifier = ET.SubElement(node, q("identifier"))
        identifier.attrib["identifierType"] = "(:tba)"
        identifier.text = "(:tba)"

    current_node = node
    for i, element in enumerate(path_elements):
        if element != ".":
            child_node = current_node.find(q(element))
            if child_node is not None:
                current_node = child_node
            else:
                current_node = ET.SubElement(current_node, q(element))

    if attribute:
        assert isinstance(value, str), f"Unsupported interpolation: Attribute {attribute} requires a string value"
        current_node.attrib[attribute] = value
    else:
        if isinstance(value, str):
            current_node.text = value
        else:
            for relpath, v in value:
                set_datacite_value(current_node, relpath, v)

    return node

# Define a function to transform data using mappings
def transform_data(args, mappings, row):
    """
    Transform data using mappings.

    Args:
        args (argparse.Namespace): Command-line arguments.
        mappings (list): List of mapping tuples.
        row (list): List of input data.

    Returns:
        dict: Transformed metadata.
    """
    metadata = {}
    datacite_root = None

    for destination, expression in mappings:
        try:
            interpolated_value = interpolate(expression, row)
            if destination.startswith("/"):
                datacite_root = set_datacite_value(datacite_root, destination, interpolated_value)
            else:
                assert isinstance(interpolated_value, str), "Unsupported interpolation: User-supplied function must return a string value in mapping to EZID metadata element"
                metadata[destination] = interpolated_value
        except AssertionError as error:
            assert False, f"{args.mappingsFile}, line {mappings.index((destination, expression)) + 1}: {str(error)}"

    if datacite_root is not None:
        if args.operation == "mint":
            shoulder = args.shoulder
        else:
            shoulder = metadata["_id"]

        identifier_type = "ARK" if shoulder.startswith("ark:/") else "DOI"
        datacite_root.findall("*[@identifierType]")[0].attrib["identifierType"] = identifier_type
        metadata["datacite"] = ET.tostring(datacite_root).decode("UTF-8")

    return metadata

# Define a function to convert metadata to ANVL format
def to_anvl(record):
    """
    Convert metadata to ANVL format.

    Args:
        record (dict): Metadata.

    Returns:
        str: Metadata in ANVL format.
    """
    def escape(s, colon_too=False):
        if colon_too:
            pattern = r"[%:\r\n]"
        else:
            pattern = r"[%\r\n]"
        return re.sub(pattern, lambda match: "%%%02X" % ord(match.group(0)), str(s))

    return "".join(f"{escape(key, True)}: {escape(value)}\n" for key, value in sorted(record.items()))

# Define a function to process a single record
def process_record(args, record):
    """
    Process a single record.

    Args:
        args (argparse.Namespace): Command-line arguments.
        record (dict): Metadata for a single record.

    Returns:
        tuple: (Identifier, Error message) or (None, None).
    """
    if args.operation == "mint":
        identifier = None
        if args.removeIdMapping and "_id" in record:
            del record["_id"]

        request = urllib.request.Request(f"https://ezid.cdlib.org/shoulder/{urllib.parse.quote(args.shoulder, ':/')}")
    else:
        identifier = str(record["_id"])
        del record["_id"]
        request = urllib.request.Request(f"https://ezid.cdlib.org/id/{urllib.parse.quote(identifier, ':/')}")
        request.get_method = lambda: "PUT" if args.operation == "create" else "POST"

    data = to_anvl(record).encode("UTF-8")
    request.data = data
    request.add_header("Content-Type", "text/plain; charset=UTF-8")
    request.add_header("Content-Length", str(len(data))

    if args.cookie:
        request.add_header("Cookie", args.cookie)
    else:
        request.add_header("Authorization", "Basic " + base64.b64encode(f"{args.username}:{args.password}".encode('utf-8')).decode('utf-8'))

    try:
        response = urllib.request.urlopen(request)
        response_data = response.read().decode("UTF-8")
        assert response_data.startswith("success:"), response_data
        return response_data[8:].split()[0], None
    except urllib.error.HTTPError as e:
        if e.fp is not None:
            response_data = e.fp.read().decode("UTF-8")
            if not response_data.startswith("error:"):
                response_data = "error: " + response_data
            return identifier, response_data
        else:
            return identifier, f"error: {e.code} {e.msg}"
    except Exception as e:
        return identifier, f"error: {str(e)}"

# Define a function to form an output row
def form_output_row(args, row, record, record_num, identifier, error):
    """
    Form an output row based on input data, metadata, and processing results.

    Args:
        args (argparse.Namespace): Command-line arguments.
        row (list): List of input data.
        record (dict): Transformed metadata.
        record_num (int): Record number in the input file.
        identifier (str): Identifier.
        error (str): Error message.

    Returns:
        list: Output row.
    """
    output_row = []
    for column in args.outputColumns:
        if isinstance(column, int):
            output_row.append(row[column])
        else:
            if column == "_n":
                output_row.append(str(record_num))
            elif column == "_id":
                output_row.append(identifier or "")
            elif column == "_error":
                output_row.append(error or "")
            else:
                output_row.append(record[column])
    return output_row

# Define a function to process input data
def process_input(args, mappings):
    """
    Process input data and generate output.

    Args:
        args (argparse.Namespace): Command-line arguments.
        mappings (list): List of mapping tuples.
    """
    class StrictTabDialect(csv.Dialect):
        delimiter = "\t"
        quoting = csv.QUOTE_NONE
        doublequote = False
        lineterminator = "\r\n"

    writer = csv.writer(sys.stdout)
    record_num = 0

    for row in csv.reader(open(args.inputFile), dialect=(StrictTabDialect if args.tabMode else csv.excel)):
        record_num += 1

        if record_num == 1:
            num_columns = len(row)
            assert max([-1] + [c for c in args.outputColumns if isinstance(c, int)]) < num_columns, "Argument -o: input column reference exceeds number of columns"

        try:
            assert len(row) == num_columns, "Inconsistent number of columns"
            row = [c for c in row]
            record = transform_data(args, mappings, row)

            if args.previewMode:
                print("\n" + to_anvl(record))
            else:
                identifier, error = process_record(args, record)
                writer.writerow(form_output_row(args, row, record, record_num, identifier, error))
                sys.stdout.flush()
        except Exception as e:
            assert False, f"Record {record_num}: {str(e)}"

# Define the main function
def main():
    try:
        parser = argparse.ArgumentParser(description="Batch registers identifiers.")
        parser.add_argument("operation", choices=["create", "mint", "update"], help="Operation to perform")
        parser.add_argument("mappingsFile", metavar="mappings", help="Configuration file")
        parser.add_argument("inputFile", metavar="input.csv", help="Input metadata in CSV form")
        parser.add_argument("-c", metavar="CREDENTIALS", dest="credentials", help="Credentials: username:password or username or session=...")
        parser.add_argument("-o", metavar="COLUMNS", dest="outputColumns", default="_n,_id,_error", help="Comma-separated list of columns to output, defaults to _n,_id,_error")
        parser.add_argument("-p", dest="previewMode", action="store_true", help="Preview mode: don't register identifiers, instead, write transformed metadata to standard output")
        parser.add_argument("-r", dest="removeIdMapping", action="store_true", help="Remove any mapping to _id; useful when temporarily minting")
        parser.add_argument("-s", metavar="SHOULDER", dest="shoulder", type=validate_shoulder, help="Shoulder to mint under, e.g., ark:/99999/fk4")
        parser.add_argument("-t", dest="tabMode", action="store_true", help="Tab mode: the input metadata is tab-separated (multiline values and tab characters in values are not supported)")
        args = parser.parse_args(sys.argv[1:])

        if not args.previewMode:
            assert args.credentials is not None, "Operation requires -c argument"

        if args.operation == "mint":
            assert args.shoulder is not None, "Operation requires -s argument"

        mappings = load_mappings(args.mappingsFile)

        if args.operation in ["create", "update"]:
            assert any(d == "_id" for d, e in mappings), "Operation requires mapping to _id"

        args.outputColumns = parse_output_columns(args.outputColumns, mappings)

        if not args.previewMode:
            if args.credentials.startswith("sessionid="):
                args.cookie = args.credentials
            else:
                args.cookie = None

                if ":" in args.credentials:
                    args.username, args.password = args.credentials.split(":", 1)
                else:
                    args.username = args.credentials
                    args.password = getpass.getpass()

        process_input(args, mappings)
    except Exception as e:
        print(traceback.format_exc())
        sys.stderr.write(f"{sys.argv[0].split('/')[-1]}: error: {str(e)}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
