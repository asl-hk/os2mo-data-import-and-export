from unittest import TestCase
from unittest.mock import Mock
from unittest.mock import patch

from parameterized import parameterized
from winrm import Session

from ..ad_common import AD
from ..ad_exceptions import CommandFailure


class MockAD(AD):
    def __init__(self):
        self.session = Mock(spec=Session)
        self.all_settings = {"primary": {"search_base": ""}}


class TestRunPSScript(TestCase):
    def setUp(self):
        super().setUp()
        self._ad = MockAD()
        self._ps_script = "not actual PowerShell code"

    @parameterized.expand(
        [
            (b'{"foo": "bar}',),
            ('{"foo": "bar}',),
        ]
    )
    def test_invalid_json_raises_exception(self, invalid_json):
        with self._mock_run_ps_response(std_out=invalid_json):
            with self.assertRaises(ValueError) as ctx:
                self._ad._run_ps_script(self._ps_script)
                # Assert that exception message contains offending part of the
                # JSON doc, as well as the script that caused the error.
                msg = ctx.exception[0]
                self.assertIn(invalid_json, msg)
                self.assertIn(str(None), msg)

    def test_nonzero_status_code_raises_exception(self):
        with self._mock_run_ps_response(status_code=42):
            with self.assertRaises(CommandFailure):
                self._ad._run_ps_script(self._ps_script)

    def test_std_out_decoding(self):
        std_out = Mock()
        with self._mock_run_ps_response(std_out=std_out):
            # Passing a `Mock` instance causes this exception:
            # "TypeError: the JSON object must be str, bytes or bytearray, not
            # Mock". However, we just want to check the encoding passed to
            # `response.std_out.decode`, so we swallow the TypeError.
            with self.assertRaises(TypeError):
                self._ad._run_ps_script(self._ps_script)
                std_out.encode.assert_called_with(AD._encoding)

    def _mock_run_ps_response(self, status_code=0, std_out=b"", std_err=b""):
        response = Mock()
        response.status_code = status_code
        response.std_out = std_out
        response.std_err = std_err
        return patch.object(self._ad.session, "run_ps", return_value=response)
