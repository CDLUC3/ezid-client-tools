from collections import OrderedDict
import re


# https://github.com/ekansa/open-context-py/blob/b611896ec75ae4eb42eba0733c307624616b7625/opencontext_py/libs/general.py#LL5C1-L5C1
class LastUpdatedOrderedDict(OrderedDict):
    """
    Stores items in the order the keys were last added
    """

    def __setitem__(self, key, value):
        if key in self:
            del self[key]
        OrderedDict.__setitem__(self, key, value)


class ANVL:
    """
    A class for working with ANVL metadata
    https://github.com/ekansa/open-context-py/blob/b611896ec75ae4eb42eba0733c307624616b7625/opencontext_py/apps/ocitems/identifiers/ezid/ezid.py#L87

    """

    def __init__(self):
        pass

    def escape_anvl(self, str_val):
        """makes ANVL safe strings by escaping certain values"""
        return re.sub("[%:\r\n]", lambda c: "%%%02X" % ord(c.group(0)), str_val)

    def parse_anvl_str(self, anvl):
        """parse an anvl string into a dictionary object of metadata"""
        metadata = LastUpdatedOrderedDict()
        for anvl_line in anvl.decode("UTF-8").splitlines():
            if ":" in anvl_line:
                line_ex = anvl_line.split(":")
                if len(line_ex) > 1:
                    esc_key = line_ex[0].strip()
                    esc_value = line_ex[1].strip()
                    key = self.unescape_anvl(esc_key).strip()
                    value = self.unescape_anvl(esc_value).strip()
                    if len(key) > 0 and len(value) > 0:
                        metadata[key] = value
        return metadata

    def unescape_anvl(self, str_val):
        """unescapes an escaped ANVL string"""
        return re.sub(
            "%([0-9A-Fa-f][0-9A-Fa-f])", lambda m: chr(int(m.group(1), 16)), str_val
        )
