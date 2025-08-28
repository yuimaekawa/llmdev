import pytest
from flask import session
from original.app import app
from original.graph import memory, get_messages_list
import os
import json
from pathlib import Path

USER_MESSAGE_1 = "1たす2は？"
USER_MESSAGE_2 = "東京駅のイベントの検索結果を教えて"

@pytest.fixture
def client():
    """
    Flaskテストクライアントを作成。
    """
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'your_secret_key'  # セッション用の秘密鍵を設定
    client = app.test_client()
    with client.session_transaction() as session:
        session.clear()  # セッションをクリアして初期化
    yield client

def test_index_get_request(client):
    """
    GETリクエストで初期画面が正しく表示されるかをテスト。
    """
    response = client.get('/')
    assert response.status_code == 200, "GETリクエストに対してステータスコード200を返すべきです。"
    assert b"<form" in response.data, "HTMLにフォーム要素が含まれている必要があります。"
    assert memory.storage == {}, "GETリクエストでメモリが初期化されるべきです。"

def test_index_post_request(client):
    """
    POSTリクエストでボットの応答が正しく返されるかをテスト。
    """
    with client.session_transaction() as session:
        thread_id = session.get('thread_id')
        assert thread_id is None, "初期状態ではセッションにthread_idが設定されていないはずです。"

    response = client.post('/', data={'user_message': USER_MESSAGE_1})
    assert response.status_code == 200, "POSTリクエストに対してステータスコード200を返すべきです。"
    decoded_data = response.data.decode('utf-8')  # バイト文字列をデコード
    assert "1たす2" in decoded_data, "ユーザーの入力がHTML内に表示されるべきです。"
    assert "3" in decoded_data, "ボットの応答が正しくHTML内に表示されるべきです。"

    with client.session_transaction() as session:
        thread_id = session.get('thread_id')
        assert thread_id is not None, "POSTリクエスト後にはセッションにthread_idが設定されているべきです。"

def test_memory_persistence_with_session(client):
    """
    複数のPOSTリクエストでメモリがセッションごとに保持されるかをテスト。
    """
    client.post('/', data={'user_message': USER_MESSAGE_1})
    client.post('/', data={'user_message': USER_MESSAGE_2})

    with client.session_transaction() as session:
        thread_id = session.get('thread_id')
        assert thread_id is not None, "セッションにはthread_idが設定されている必要があります。"

    messages = get_messages_list(memory, thread_id)
    assert len(messages) >= 2, "メモリに2つ以上のメッセージが保存されるべきです。"
    assert any("1たす2" in msg['text'] for msg in messages if msg['class'] == 'user-message'), "メモリに最初のユーザーメッセージが保存されるべきです。"
    assert any("東京駅" in msg['text'] for msg in messages if msg['class'] == 'user-message'), "メモリに2番目のユーザーメッセージが保存されるべきです。"

def test_clear_endpoint(client):
    """
    /clearエンドポイントがセッションとメモリを正しくリセットするかをテスト。
    """
    client.post('/', data={'user_message': USER_MESSAGE_1})

    with client.session_transaction() as session:
        thread_id = session.get('thread_id')
        assert thread_id is not None, "POSTリクエスト後にはセッションにthread_idが設定されているべきです。"

    response = client.post('/clear')
    assert response.status_code == 200, "POSTリクエストに対してステータスコード200を返すべきです。"
    assert b"<form" in response.data, "HTMLにフォーム要素が含まれている必要があります。"

    with client.session_transaction() as session:
        thread_id = session.get('thread_id')
        assert thread_id is None, "/clearエンドポイント後にはセッションにthread_idが設定されていないべきです。"

    # メモリがクリアされているか確認
    cleared_messages = memory.get({"configurable": {"thread_id": thread_id}})
    assert cleared_messages is None, "メモリは/clearエンドポイント後にクリアされるべきです。"

def test_save_chat_history_creates_json_file(client):
    """
    /saveエンドポイントがチャット履歴をJSONファイルに保存できるかをテスト。
    """
    # チャット1回
    client.post('/', data={'user_message': USER_MESSAGE_1})

    # スレッドID取得
    with client.session_transaction() as session:
        thread_id = session.get('thread_id')
        assert thread_id is not None, "スレッドIDがセッションに存在する必要があります。"

    # /save エンドポイントへPOST
    response = client.post('/save')
    assert response.status_code == 200, "/save エンドポイントはステータスコード200を返すべきです。"

    # 保存されたファイルの存在を確認
    save_path = Path(f'chat_logs/{thread_id}.json')
    assert save_path.exists(), f"chat_logs/{thread_id}.json が保存されている必要があります。"

    # ファイル内容を検証
    with open(save_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        assert isinstance(data, list), "保存されたデータはリスト形式である必要があります。"
        assert any("1たす2" in msg.get("data", {}).get("content", "") for msg in data), "ユーザーの発言が保存ファイルに含まれている必要があります。"

    # テスト後の後始末
    os.remove(save_path)

def test_load_chat_history_restores_memory(client):
    """
    /loadエンドポイントが保存されたチャット履歴を正しく読み込むかをテスト。
    """
    # 1. チャット履歴を作る
    client.post('/', data={'user_message': USER_MESSAGE_1})

    # 2. thread_idを取得
    with client.session_transaction() as session:
        thread_id = session.get('thread_id')
        assert thread_id is not None, "セッションにthread_idが存在する必要があります。"

    # 3. /save で履歴を保存
    save_path = Path(f'chat_logs/{thread_id}.json')
    response = client.post('/save')
    assert response.status_code == 200
    assert save_path.exists(), "保存ファイルが存在する必要があります。"

    # 4. メモリとセッションをリセット（履歴がなくなることを確認）
    client.post('/clear')
    with client.session_transaction() as session:
        assert session.get('thread_id') is None, "セッションがリセットされている必要があります。"

    # 5. /load に thread_id をPOSTして履歴を復元
    response = client.post('/load', data={'thread_id': thread_id})
    assert response.status_code == 200, "/load エンドポイントはステータスコード200を返すべきです。"

    # 6. 再びthread_idをセッションから取得
    with client.session_transaction() as session:
        restored_id = session.get('thread_id')
        assert restored_id == thread_id, "復元後も同じthread_idが保持されているべきです。"

    # 7. メモリが復元されていることを確認
    messages = get_messages_list(memory, thread_id)
    assert len(messages) >= 2, "読み込んだメッセージがメモリに復元されている必要があります。"
    assert any("1たす2" in msg['text'] for msg in messages if msg['class'] == 'user-message'), "元のユーザーメッセージが復元されている必要があります。"

    # 8. 後始末：保存ファイルを削除
    os.remove(save_path)
