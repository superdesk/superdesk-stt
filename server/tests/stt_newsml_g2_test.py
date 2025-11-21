from stt.publish.stt_newsml_g2 import format_filename


def test_format_filename():
    assert "foo.jpg" == format_filename("foo.jpg", ".jpg")
    assert "foo.jpg" == format_filename("foo", ".jpg")
    assert "foo.jpg" == format_filename("test/foo.jpeg", ".jpg")
