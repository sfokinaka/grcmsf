from flask import Flask, render_template, request, redirect, url_for, session, flash
from simple_salesforce import Salesforce
import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# -----------------------------
# Flask アプリ
# -----------------------------
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "super-secret-key")

JST = timezone(timedelta(hours=9))

# -----------------------------
# Salesforce 接続
# -----------------------------
SF_USERNAME = os.getenv("SF_USERNAME")
SF_PASSWORD = os.getenv("SF_PASSWORD")
SF_SECURITY_TOKEN = os.getenv("SF_SECURITY_TOKEN")

sf = Salesforce(
    username=SF_USERNAME,
    password=SF_PASSWORD,
    security_token=SF_SECURITY_TOKEN,
    domain="login"
)
# -----------------------------
# ログインチェック関数
# -----------------------------
def check_login(username, password):
    # APID__c または Name で検索
    soql = f"""
        SELECT Id, Name, APID__c, Field8__c, Field9__c, Field10__c
        FROM CustomObject1__c
        WHERE (APID__c = '{username}' OR Name = '{username}')
        LIMIT 1
    """
    result = sf.query(soql)
    print(result)
    if result["totalSize"] == 0:
        return None

    user = result["records"][0]

    # パスワードチェック
    if user.get("Field8__c") == password:
        return {
            "id": user["Id"],
            "name": user.get("Name"),
            "apid": user.get("APID__c"),
            "company": user.get("Field9__c"),
            "owner_id1": user.get("Field10__c")
        }
    else:
        return None



# -----------------------------
# ログイン画面
# -----------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = check_login(username, password)
        if user:
            session["user"] = user
            session["last_activity"] = datetime.now(JST).isoformat()
            flash("ログイン成功しました")
            return redirect(url_for("menu"))
        else:
            flash("ユーザー名またはパスワードが間違っています")

    return render_template("login.html")

# -----------------------------
# メニュー画面
# -----------------------------
@app.route("/menu")
def menu():
    user = session.get("user")
    if not user:
        flash("ログインしてください")
        return redirect(url_for("login"))

    return render_template("menu.html", username=user["name"], company=user["company"])

# -----------------------------
# ログアウト
# -----------------------------
@app.route("/logout")
def logout():
    session.clear()
    flash("ログアウトしました")
    return redirect(url_for("login"))

# -----------------------------
# 取次可能商材
# -----------------------------
@app.route("/products")
def products():
    user = session.get("user")
    if not user:
        flash("ログインしてください")
        return redirect(url_for("login"))

    company = user["company"]  # Field9__c の販社名

    # 複数選択ピックリストに company を含む商材を検索
    soql = f"""
        SELECT Id, Name, Field1__c, Field2__c, Field6__c
        FROM CustomObject3__c
        WHERE Field6__c includes ('{company}')
    """
    result = sf.query(soql)
    records = result.get("records", [])

    return render_template("products.html", products=records, company=company)


@app.route("/account/new", methods=["GET"])
def new_account():
    user = session.get("user")
    if not user:
        flash("ログインしてください")
        return redirect(url_for("login"))

    company = user["company"]

    # 取次可能商材を取得
    soql = f"""
        SELECT Id, Name, Field1__c, Field2__c
        FROM CustomObject3__c
        WHERE Field6__c includes ('{company}')
    """
    result = sf.query(soql)
    products = result.get("records", [])

    # Salesforce picklist 取得用
    field_desc = sf.Account.describe()["fields"]
    picklists = {}
    picklist_fields = [
        "Field72__c",  # 取次種別
        "Field28__c",  # 固定申込
        "Field7__c",   # 性別
        "Field20__c",  # 利用回線
        "Field22__c",  # 利用携帯Ⅰ
        "Field23__c",  # 携帯台数Ⅰ
        "Field36__c",  # KDDI提供エリア判定
        "Field112__c"  # MS光WEB判定結果
    ]
    for f in field_desc:
        if f["name"] in picklist_fields:
            picklists[f["name"]] = [p["value"] for p in f.get("picklistValues", []) if not p.get("inactive", False)]

    # ==============================
    # 自分の販社用テンプレを取得
    # ==============================
    templates_raw = sf.query_all(
        f"SELECT Name, Field1__c, Field2__c FROM CustomObject5__c WHERE Field2__c = '{company}'"
    )["records"]
    templates = [{"name": t["Name"], "content": t["Field1__c"]} for t in templates_raw]

    return render_template(
        "account_form.html",
        products=products,
        picklists=picklists,
        templates=templates,  # ← ここで渡す
        user=user
    )

# -----------------------------
# 取引先レコード作成送信
# -----------------------------
@app.route("/account/create", methods=["POST"])
def create_account():
    user = session.get("user")
    if not user:
        flash("ログインしてください")
        return redirect(url_for("login"))

    # フォームからまとめて取得（HTML name 属性に合わせる）
    record_data = {
        "Name": request.form.get("Name"),
        "X2__c": request.form.get("X2__c"),
        "Field28__c": request.form.get("Field28__c"),
        "Field52__c": request.form.get("Field52__c"),
        "Field59__c": request.form.get("Field59__c"),
        "Field60__c": request.form.get("Field60__c"),
        "Field60__c": request.form.get("Field162__c"),
        "Field53__c": request.form.get("Field53__c"),
        "Field1__c": request.form.get("Field1__c"),
        "Field2__c": request.form.get("Field2__c"),
        "Field3__c": request.form.get("Field3__c"),
        "Field4__c": request.form.get("Field4__c"),
        "Field8__c": request.form.get("Field8__c"),
        "Field7__c": request.form.get("Field7__c"),
        "Field20__c": request.form.get("Field20__c"),
        "Field22__c": request.form.get("Field22__c"),
        "Field23__c": request.form.get("Field23__c"),
        "Field36__c": request.form.get("Field36__c"),
        "Field37__c": request.form.get("Field37__c"),
        "Field112__c": request.form.get("Field112__c"),
        "Field35__c": request.form.get("Field35__c"),
        "ShippingPostalCode": request.form.get("ShippingPostalCode"),
        "ShippingState": request.form.get("ShippingState"),
        "ShippingCity": request.form.get("ShippingCity"),
        "ShippingStreet": request.form.get("ShippingStreet"),
        "Field10__c": request.form.get("Field10__c"),
        "Field11__c": request.form.get("Field11__c"),
        "Field12__c": request.form.get("Field12__c"),
        "Field13__c": request.form.get("Field13__c"),
        "Field14__c": request.form.get("Field14__c"),
        "Field72__c": request.form.get("Field72__c"),
        "Field70__c": request.form.get("Field70__c"), 
        "OwnerId": user.get("owner_id1"),
        "Field71__c": user["id"],
        "Field75__c": user.get("company")
    }

    # 必須チェック
    if not record_data["Name"] or not record_data["Field72__c"] or not record_data["Field70__c"]:
        flash("必須項目を入力してください")
        return redirect(url_for("new_account"))

    # OwnerId チェック
    owner_id = record_data["OwnerId"]
    if owner_id is None or owner_id.strip() == "":
        return render_template(
            "result.html",
            success=False,
            message="レコード所有者が設定されていません (Field10__c が空です)",
            record_name=record_data["Name"],
            user=user
        )

    # Salesforce にレコード作成
    try:
        record = sf.Account.create(record_data)
        return render_template(
            "result.html",
            success=True,
            message=f"取引先レコード作成成功！ ID: {record['id']}",
            record_name=record_data["Name"],
            user=user
        )
    except Exception as e:
        return render_template(
            "result.html",
            success=False,
            message=f"Account 作成中にエラーが発生しました: {str(e)}",
            record_name=record_data["Name"],
            user=user
        )


# -----------------------------
# 自分の案件一覧
# -----------------------------
@app.route("/my_accounts")
def my_accounts():
    user = session.get("user")
    if not user:
        flash("ログインしてください")
        return redirect(url_for("login"))

    keyword = request.args.get("keyword", "")
    selected_status = request.args.get("status", "")

    soql = f"""
        SELECT Id, Name, Field70__c, Field70__r.Name, Field59__c, Field60__c, Field54__c,
               CreatedDate, Field131__c, Field90__c, Field65__c, Field57__c
        FROM Account
        WHERE Field71__c = '{user["id"]}'
    """
    if keyword:
        soql += f" AND Name LIKE '%{keyword}%'"
    if selected_status:
        soql += f" AND Field54__c = '{selected_status}'"

    result = sf.query(soql)
    accounts = result.get("records", [])

    # 前確ステータスの選択肢を取得
    picklists = sf.Account.describe()["fields"]
    status_options = []
    for f in picklists:
        if f["name"] == "Field54__c":
            status_options = [p["value"] for p in f.get("picklistValues", []) if not p.get("inactive", False)]

    return render_template(
        "my_accounts.html",
        accounts=accounts,
        keyword=keyword,
        status_options=status_options,
        selected_status=selected_status
    )

@app.route("/account/edit/<account_id>")
def edit_account(account_id):
    soql = f"""
        SELECT Id, Name, Field70__c, Field70__r.Name, Field59__c, Field60__c, Field54__c, Description
        FROM Account
        WHERE Id = '{account_id}'
    """
    result = sf.query(soql)
    if not result['records']:
        flash("案件が見つかりません")
        return redirect(url_for("my_accounts"))

    account = result['records'][0]

    # ピックリスト取得
    field_desc = sf.Account.describe()["fields"]
    picklists = {}
    for f in field_desc:
        if f["name"] in ["Field54__c"]:
            picklists[f["name"]] = [p["value"] for p in f.get("picklistValues", []) if not p.get("inactive", False)]

    return render_template("edit_account.html", account=account, picklists=picklists)



@app.route("/account/update/<account_id>", methods=["POST"])
def update_account(account_id):
    user = session.get("user")
    if not user:
        flash("ログインしてください")
        return redirect(url_for("login"))
    
    # フォームから時間取得（HH:MM形式）
    time_str = request.form.get("Field60__c")  # ex: "08:30"
    if time_str:
        # datetime オブジェクトに変換（秒は 0 にする）
        dt = datetime.strptime(time_str, "%H:%M")
        dt = dt.replace(second=0)
        # JST → UTC に変換
        dt_utc = dt - timedelta(hours=0)
        # Salesforce Time 型用の文字列に変換
        field60_value = dt_utc.strftime("%H:%M:%S.000Z")
    else:
        # 空欄の場合は 00:00:00
        field60_value = "00:00:00.000Z"

    update_data = {
        "Field59__c": request.form.get("Field59__c"),
        "Field60__c": field60_value,
        "Field54__c": request.form.get("Field54__c"),
    }
    call_result = request.form.get("call_result")

    # 案件更新
    sf.Account.update(account_id, update_data)

    # 活動記録(Task作成)
    sf.Task.create({
        "Subject": "電話",
        "OwnerId": "005GA00000AbMOaYAN",
        "ActivityDate": datetime.now(JST).date().isoformat(),
        "WhatId": account_id,         # 関連先
        "Status": "Completed",
        "Field1__c": "架電",
        "Field2__c": "営業架電",
        "Field3__c": call_result,
        "Description": request.form.get("Description")
    })

    flash("案件を更新し、活動記録を作成しました")
    return redirect(url_for("my_accounts"))


# -----------------------------
# セッション有効期限チェック
# -----------------------------
@app.before_request
def make_session_permanent():
    session.permanent = True
    app.permanent_session_lifetime = timedelta(hours=1)

    last_activity = session.get("last_activity")
    if last_activity:
        last_time = datetime.fromisoformat(last_activity)
        if datetime.now(JST) - last_time > timedelta(hours=1):
            session.clear()
            flash("1時間無操作のため、再ログインしてください")
            return redirect(url_for("login"))

    session["last_activity"] = datetime.now(JST).isoformat()


@app.route("/")
def index():
    return redirect(url_for("login"))



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Render が割り当てたポートを取得
    app.run(host="0.0.0.0", port=port, debug=True)

