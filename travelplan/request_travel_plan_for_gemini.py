import configparser
from logging import DEBUG
from flask import Flask, render_template, request
import mysql.connector
import google.generativeai as genai

"""
モジュール名 request_travel_plan_for_gemini

Author: y-t
Since: 2024/03/17
アプリ概要: GeminiApiを使用して旅行プランの提案をするアプリ
"""

application = Flask(__name__)

application.logger.setLevel(DEBUG)


@application.route('/')
def input_page():
    # 入力画面表示
    application.logger.info('★TravelRequestForGemini:入力画面出力')
    return render_template('input.html')


config_ini = configparser.ConfigParser()
config_ini.read('/application_dir/travelplan/travelplan/config.ini', encoding='utf-8')


@application.route('/result', methods=['GET', 'POST'])
def request_api_process():
    application.logger.info('★TravelRequestForGemini:リクエスト処理開始')
    if request.method == 'POST':
        # リクエストがPOSTの場合
        # 入力画面からの値取得
        prefecture = request.form.get('prefecture')
        day = request.form.get('day')

        # 入力が不正の場合
        if prefecture == '都道府県を選択してください' or day == '予定日数を選択してください':
            application.logger.info('★TravelRequestForGemini:入力画面出力(入力不正)')
            return render_template('input.html')

        # prompt生成
        prompt = prefecture + "へ" + day + "日間旅行するプランを提案してください。"
        application.logger.info('★TravelRequestForGemini:リクエストPrompt[' + prompt + ']')

        # リクエスト処理実行
        processed_result = request_gemini_api(prompt)

        if processed_result == "false":
            # リクエスト処理が失敗した場合
            processed_result = "API実行に失敗しました。時間をおいて再実行してください。"

        # 結果をHTMLテンプレートに差し込んで表示
        application.logger.info('★TravelRequestForGemini結果画面出力')
        return render_template('result.html', result=processed_result)

    # POST以外のリクエストの場合
    application.logger.info('★TravelRequestForGemini:入力画面出力(POST以外)')
    return render_template('input.html')


def request_gemini_api(prompt):
    try:
        application.logger.info('★TravelRequestForGemini:APIリクエスト処理開始')

        # プロンプトを登録
        register_result = resister_request_info(prompt)

        # 登録失敗時はfalseを返却
        if register_result == "false":
            return "false"

        # リクエスト数のチェック(1分間に60リクエスト以内にする対策)
        check_result = check_request_count()

        # チェック失敗時・例外時はfalseを返却
        if check_result == "false":
            return "false"

        # API呼び出し処理
        GOOGLE_API_KEY = config_ini.get('API-SETTINGS', 'apikey')
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel(config_ini.get('API-SETTINGS', 'model'))
        api_result = model.generate_content(prompt).text

        # 結果を返却
        return api_result

    except Exception as e:
        # エラー時はFalse返却
        application.logger.error('!!★!!TravelRequestForGemini:APIリクエスト処理でexception発生[' + str(e) + ']')
        return "false"


def resister_request_info(prompt):
    try:
        application.logger.info('★TravelRequestForGemini:リクエスト情報登録処理開始')

        # MySQLに接続
        conn = mysql.connector.connect(
            host=config_ini.get('DBSETTINGS', 'host'),
            user=config_ini.get('DBSETTINGS', 'user'),
            password=config_ini.get('DBSETTINGS', 'password'),
            database=config_ini.get('DBSETTINGS', 'database')
        )
        # カーソルを作成
        cursor = conn.cursor()

        # クエリ実行
        query = "insert into gemini_request_info ( request_prompt, kind ) values ( %s, 10 );"
        cursor.execute(query, (prompt,))

        # コミットとカーソルと接続をクローズ
        cursor.close()
        conn.commit()
        conn.close()

        application.logger.info('★TravelRequestForGemini:リクエスト情報登録処理終了')
        # 成功時時はtrue返却
        return "true"

    except Exception as e:
        # エラー時はFalse返却
        application.logger.error('!!★!!TravelRequestForGemini:リクエスト情報登録処理でexception発生[' + str(e) + ']')
        return "false"


def check_request_count():
    try:
        application.logger.info('★TravelRequestForGemini:リクエスト情報チェック処理開始')

        # MySQLに接続
        conn = mysql.connector.connect(
            host=config_ini.get('DBSETTINGS', 'host'),
            user=config_ini.get('DBSETTINGS', 'user'),
            password=config_ini.get('DBSETTINGS', 'password'),
            database=config_ini.get('DBSETTINGS', 'database')
        )

        # カーソルを作成
        cursor = conn.cursor()

        # クエリ実行
        query = "select count(*) from gemini_request_info where create_date >= now() - interval 1 minute;"
        cursor.execute(query)

        # 結果を取得
        count_result = cursor.fetchone()
        count = count_result[0]

        # カーソルと接続をクローズ
        cursor.close()
        conn.close()

        application.logger.info('★TravelRequestForGemini:リクエスト情報チェック処理終了[カウント=' + str(count) + ']')

        # 1分間に60以上のリクエストがあればfalse返却
        if count >= 60:
            return "false"
        else:
            return "true"

    except Exception as e:
        # エラー時はFalse返却
        application.logger.error(
            '!!★!!TravelRequestForGemini:リクエスト情報チェック処理でexception発生[' + str(e) + ']')
        return 'false'


if __name__ == '__main__':
    application.run(debug=True, host='0.0.0.0')
