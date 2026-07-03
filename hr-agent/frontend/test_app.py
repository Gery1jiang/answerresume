from flask import Flask, render_template_string

app = Flask(__name__)
app.secret_key = 'test'

HTML_CONTENT = """
<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body>
    <div id="step1">Step 1 - 口令验证</div>
    <div id="step2">
        <div class="chat-header">Header</div>
        <div class="welcome-section">
            <div class="welcome-greeting">您好，欢迎您的到来</div>
            <div class="welcome-intro">正在加载个人信息...</div>
            <div class="quick-questions">
                <button>问题1</button>
                <button>问题2</button>
            </div>
        </div>
        <div class="chat-history">Chat</div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_CONTENT)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=51671, debug=True)