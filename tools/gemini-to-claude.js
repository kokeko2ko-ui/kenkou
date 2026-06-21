(function () {
  var lines = [];

  // Gemini のカスタム要素を取得
  var userEls = Array.from(document.querySelectorAll('user-query'));
  var modelEls = Array.from(document.querySelectorAll('model-response'));

  if (userEls.length === 0 && modelEls.length === 0) {
    // フォールバック: 代替セレクタ
    userEls = Array.from(document.querySelectorAll(
      '[data-role="user"], .query-text, .user-message, [class*="UserMessage"]'
    ));
    modelEls = Array.from(document.querySelectorAll(
      '[data-role="model"], .response-text, .model-message, [class*="ModelResponse"]'
    ));
  }

  if (userEls.length === 0 && modelEls.length === 0) {
    // 最終フォールバック: ページ全体テキスト
    var main = document.querySelector('main, [role="main"], .conversation') || document.body;
    var raw = main.innerText.trim();
    navigator.clipboard.writeText(raw).then(function () {
      alert('⚠️ 会話要素が見つからなかったためページ全体をコピーしました。\nClaudeに貼り付けてください。');
    });
    return;
  }

  // 位置情報で全要素をソート（会話順）
  var all = userEls.map(function (el) { return { el: el, role: 'user' }; })
    .concat(modelEls.map(function (el) { return { el: el, role: 'model' }; }));

  all.sort(function (a, b) {
    var ar = a.el.getBoundingClientRect();
    var br = b.el.getBoundingClientRect();
    return (ar.top + window.scrollY) - (br.top + window.scrollY);
  });

  // ページを一番上に戻して再計算（スクロール位置問題を回避）
  // 代わりに DOM順でソート
  var allDomSorted = Array.from(document.querySelectorAll(
    'user-query, model-response, [data-role="user"], [data-role="model"]'
  ));

  if (allDomSorted.length > 0) {
    lines = allDomSorted.map(function (el) {
      var tag = el.tagName.toLowerCase();
      var role = el.getAttribute('data-role');
      var isUser = tag === 'user-query' || role === 'user';
      var label = isUser ? '【ユーザー】' : '【Gemini】';
      var text = el.innerText.trim();
      return text ? label + '\n' + text : null;
    }).filter(Boolean);
  } else {
    lines = all.map(function (item) {
      var label = item.role === 'user' ? '【ユーザー】' : '【Gemini】';
      var text = item.el.innerText.trim();
      return text ? label + '\n' + text : null;
    }).filter(Boolean);
  }

  var output = '=== Gemini 会話 ===\n\n' + lines.join('\n\n---\n\n');

  navigator.clipboard.writeText(output).then(function () {
    alert('✅ ' + lines.length + ' ターンをコピーしました！\nClaudeに貼り付けてください。');
  }).catch(function () {
    // clipboard API が使えない場合のフォールバック
    var ta = document.createElement('textarea');
    ta.value = output;
    ta.style.position = 'fixed';
    ta.style.top = '0';
    ta.style.left = '0';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    try {
      document.execCommand('copy');
      alert('✅ コピーしました！Claudeに貼り付けてください。');
    } catch (e) {
      alert('❌ コピー失敗。手動でテキストを選択してコピーしてください。');
    }
    document.body.removeChild(ta);
  });
})();
