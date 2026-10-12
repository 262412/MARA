"""Remote tool metadata is text inside the existing HTML status wrapper."""

from html.parser import HTMLParser

from kotaemon.agents.tools.mcp import format_tool_list


def test_remote_metadata_cannot_create_html_elements():
    class Elements(HTMLParser):
        tags = []

        def handle_starttag(self, tag, attrs):
            self.tags.append(tag)

    name = '<img src=x onerror="owned()">'
    description = '<script>owned()</script> & "quoted"'
    result = format_tool_list([{"name": name, "description": description}], [name])
    parser = Elements()
    parser.feed(result)
    assert set(parser.tags) <= {"b", "br", "i", "code"}
    assert "&lt;img" in result and "&lt;script&gt;" in result
    assert "1/1 tool(s) enabled" in result
