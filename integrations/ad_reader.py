import os
import json
from winrm import Session

WINRM_HOST = os.environ.get('WINRM_HOST', None)
AD_SYSTEM_USER = os.environ.get('AD_SYSTEM_USER', None)
AD_PASSWORD = os.environ.get('AD_PASSWORD', None)
# SEARCH_BASE
# PROPERTIES
# SKIP_BRUGERTYPE


class ADParameterReader(object):

    def __init__(self):
        self.ad_system_user = AD_SYSTEM_USER
        self.ad_password = AD_PASSWORD
        self.winrm_host = WINRM_HOST

        self.session = Session(
            'http://' + self.winrm_host + ':5985/wsman',
            transport='kerberos',
            auth=(None, None)
        )

    def _run_ps_script(self, ps_script):
        """
        Run a power shell script and return the result. If it fails, the
        error is returned in its raw form.
        :param ps_script: The power shell script to run.
        :return: A dictionary with the returned parameters.
        """
        r = self.session.run_ps(ps_script)
        if r.status_code == 0:
            if r.std_out:
                response = json.loads(r.std_out.decode('Latin-1'))
            else:
                response = {}
        else:
            response = r.std_err
        return response

    def _build_user_credential(self):
        """
        Build the commonn set of Power Shell commands that is needed to
        run the AD commands.
        :return: A suitable string to prepend to AD commands.
        """
        credential_template = """
        $User = "{}"
        $PWord = ConvertTo-SecureString –String "{}" –AsPlainText -Force
        $TypeName = "System.Management.Automation.PSCredential"
        $UserCredential = New-Object –TypeName $TypeName –ArgumentList $User, $PWord
        """
        user_credential = credential_template.format(AD_SYSTEM_USER, AD_PASSWORD)
        return user_credential

    def read_encoding(self):
        """
        Read the character encoding of the Power Shell session.
        """
        ps_script = "$OutputEncoding | ConvertTo-Json"
        response = self._run_ps_script(ps_script)
        return response

    def read_user(self, user=None, cpr=None):
        """
        Read all properties of an AD user. The user can be retrived either by cpr
        or by AD user name.
        :param user: The AD username to retrive.
        :param cpr: cpr number of the user to retrive.
        :return: All properties listed in AD for the user.
        """
        if (not cpr) and (not user):
            return
        if user:
            ps_template = "get-aduser {}"
            get_command = ps_template.format(user)
        if cpr:
            ps_template = "get-aduser -Filter 'xAttrCPR -like \"{}\"'"
            get_command = ps_template.format(cpr)
        # properties = ' -Properties *'
        properties = (' -SearchBase "OU=Kommune,DC=viborg,DC=local" -Properties ' +
                      ' xAttrCPR,ObjectGuid,SamAccountName,Title,Name,xBrugertype')
        command_end = ' -Credential $usercredential | ConvertTo-Json'

        ps_script = (self._build_user_credential() +
                     get_command +
                     properties +
                     command_end)
        response = self._run_ps_script(ps_script)

        if isinstance(response, list):
            unique = False
            for current_user in response:
                job_title = current_user.get('Title')
                if job_title and job_title.find('FRATR') == 0:
                    continue # These are users that has left
                if current_user['xBrugertype'] == 'Medarbejder':
                    user = current_user
                    assert(not unique)
                    unique = True
            assert(unique)
        else:
            user = response
        return user

if __name__ == '__main__':
    ad_reader = ADParameterReader()
    # print(ad_reader.read_encoding())
    user = ad_reader.read_user(user='konroje')
    print()
    print(sorted(user.keys()))
    print(user['xBrugertype'])
    print(user['ObjectGuid'])
