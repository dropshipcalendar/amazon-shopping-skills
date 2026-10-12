"""Local-machine Windows vault entries without keyring's duplicate-on-write behavior."""


class WindowsCredentialStore:
    def __init__(self, api, error_type):
        self.api = api
        self.error_type = error_type

    @classmethod
    def native(cls):
        from win32ctypes.pywin32 import pywintypes, win32cred
        return cls(win32cred, pywintypes.error)

    @staticmethod
    def target(service, username):
        return f"{service}/local/{username}"

    @staticmethod
    def legacy_target(service, username):
        return f"{username}@{service}"

    def _read(self, target):
        try:
            return self.api.CredRead(TargetName=target, Type=self.api.CRED_TYPE_GENERIC)
        except self.error_type as exc:
            if exc.winerror == 1168:  # ERROR_NOT_FOUND only; never hide denial.
                return None
            raise

    @staticmethod
    def _value(record):
        blob = record["CredentialBlob"]
        try:
            return blob.decode("utf-16")
        except UnicodeDecodeError:
            return blob.decode("utf-8")

    def get_password(self, service, username):
        # Current entries take precedence. In the legacy format the shared
        # base entry is newer than any legacy compound copy.
        for target in (self.target(service, username), service, self.legacy_target(service, username)):
            record = self._read(target)
            if record and record["UserName"] == username:
                return self._value(record)
        return None

    def set_password(self, service, username, password):
        target = self.target(service, username)
        self.api.CredWrite({
            "Type": self.api.CRED_TYPE_GENERIC,
            "TargetName": target,
            "UserName": username,
            "CredentialBlob": password,
            "Comment": "Amazon shopping skill credential",
            "Persist": self.api.CRED_PERSIST_LOCAL_MACHINE,
        }, 0)
        # Never remove an old value before the replacement write succeeds.
        # A different username in the shared legacy slot belongs to another
        # credential and must remain until that credential is migrated.
        legacy = self._read(service)
        if legacy and legacy["UserName"] == username:
            self._delete(service)
        old_copy = self._read(self.legacy_target(service, username))
        if old_copy and old_copy["UserName"] == username:
            self._delete(self.legacy_target(service, username))

    def _delete(self, target):
        try:
            self.api.CredDelete(TargetName=target, Type=self.api.CRED_TYPE_GENERIC)
        except self.error_type as exc:
            if exc.winerror != 1168:
                raise

    def delete_password(self, service, username):
        for target in (self.target(service, username), service, self.legacy_target(service, username)):
            record = self._read(target)
            if record and record["UserName"] == username:
                self._delete(target)
