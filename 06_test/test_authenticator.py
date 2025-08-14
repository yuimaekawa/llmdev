import pytest
from authenticator import Authenticator

@pytest.fixture
def authenticator():
    auth = Authenticator()
    yield auth

def test_register(authenticator):
    authenticator.register("user1", "pass1")
    assert authenticator.users["user1"] == "pass1"

def test_register_existing(authenticator):
    authenticator.register("user1", "pass1")
    with pytest.raises(ValueError, match="エラー: ユーザーは既に存在します。"):
        authenticator.register("user1", "pass2")
    
def test_login(authenticator):
    authenticator.register("user1", "pass1")
    assert authenticator.login("user1", "pass1") == "ログイン成功"

def test_login_error(authenticator):
    authenticator.register("user1", "pass1")
    with pytest.raises(ValueError, match="エラー: ユーザー名またはパスワードが正しくありません。"):
        authenticator.login("user1", "pass2")