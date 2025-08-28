# VS Codeのデバッグ実行で `from chatbot.graph` でエラーを出さない対策
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uuid
from flask import Flask, render_template, request, make_response, session 
from original.graph import get_bot_response, get_messages_list, memory, graph, get_saved_thread_ids, build_graph
import json
from langchain_core.messages import messages_from_dict, messages_to_dict, HumanMessage

# Flaskアプリケーションのセットアップ
app = Flask(__name__)
app.secret_key = 'your_secret_key'  # セッション用の秘密鍵

# 使用するモデル名
MODEL_NAME = "gpt-4o-mini" 

@app.route('/', methods=['GET', 'POST'])
def index():

    # セッションからthread_idを取得、なければ新しく生成してセッションに保存
    if 'thread_id' not in session:
        session['thread_id'] = str(uuid.uuid4())  # ユーザー毎にユニークなIDを生成

    # GETリクエスト時は初期メッセージ表示
    if request.method == 'GET':
        # メモリをクリア
        memory.storage.clear()
        return render_template('index.html', messages=[], saved_threads=get_saved_thread_ids())
        # response = make_response(render_template('index.html', messages=[]))
        # return response

    # ユーザーからのメッセージを取得
    user_message = request.form['user_message']
    
    # ボットのレスポンスを取得（メモリに保持）
    get_bot_response(user_message, memory, session['thread_id'])

    # メモリからメッセージの取得
    messages = get_messages_list(memory, session['thread_id'])

    # レスポンスを返す
    return make_response(render_template('index.html', messages=messages, saved_threads=get_saved_thread_ids()))

@app.route('/clear', methods=['POST'])
def clear():
    # セッションからthread_idを削除
    session.pop('thread_id', None)

    # メモリをクリア
    memory.storage.clear()
    # 対話履歴を初期化
    response = make_response(render_template('index.html', messages=[], saved_threads=get_saved_thread_ids()))
    return response

@app.route('/save', methods=['POST'])
def save():
    thread_id = session.get('thread_id')
    if thread_id:
        logs = memory.get({"configurable": {"thread_id": thread_id}})['channel_values']['messages']
        os.makedirs('chat_logs', exist_ok=True)
        save_path = f'chat_logs/{thread_id}.json'
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(messages_to_dict(logs), f, ensure_ascii=False, indent=2)
    return make_response(render_template('index.html', messages=get_messages_list(memory, thread_id), saved_threads=get_saved_thread_ids()))

@app.route('/load', methods=['POST'])
def load():
    thread_id = request.form.get('thread_id')
    session['thread_id'] = thread_id
    filepath = f'chat_logs/{thread_id}.json'
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            message_dicts = json.load(f)
            messages = messages_from_dict(message_dicts)

            # メモリを一度クリアしてから履歴を順に再生（手動注入の代替）
            memory.storage.clear()

            # graphが存在しなければ作る（初回用）
            global graph
            if graph is None:
                graph = build_graph(MODEL_NAME, memory)

            # 履歴のHumanMessageだけを順に再実行
            for msg in messages:
                if isinstance(msg, HumanMessage):
                    graph.invoke(
                        {"messages": [("user", msg.content)]},
                        {"configurable": {"thread_id": thread_id}},
                        stream_mode="values"
                    )
            
    return make_response(render_template('index.html', messages=get_messages_list(memory, thread_id), saved_threads=get_saved_thread_ids()))

if __name__ == '__main__':
    app.run(debug=True)