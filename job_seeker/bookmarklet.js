// ==UserScript==
// 在 BOSS直聘搜索结果页面 F12 → Console 执行
// 自动提取当前页面的岗位信息并保存到系统
// ==/UserScript==

(async function() {
  const API_URL = 'http://localhost:51666';

  // 1. Login to get token
  const loginResp = await fetch(API_URL + '/admin/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'admin', password: 'admin123' })
  });
  const { access_token } = await loginResp.json();
  if (!access_token) {
    console.error('❌ 登录后端失败');
    return;
  }
  console.log('✅ 后端登录成功');

  // 2. Extract job cards from current page
  const cards = document.querySelectorAll('.job-card-wrapper');
  if (!cards.length) {
    console.warn('⚠️ 未找到岗位卡片，请确认你在 BOSS直聘搜索结果页');
    return;
  }

  const jobs = [];
  for (const card of cards) {
    try {
      const title = card.querySelector('.job-name')?.textContent?.trim() || '';
      const company = card.querySelector('.company-name')?.textContent?.trim() || '';
      const salary = card.querySelector('.salary')?.textContent?.trim() || '';
      const city = card.querySelector('.job-area')?.textContent?.trim() || '';
      const link = card.querySelector('a.job-card-link')?.getAttribute('href') || '';
      jobs.push({
        platform: 'boss',
        title,
        company,
        city,
        salary,
        jd_url: link ? 'https://www.zhipin.com' + link : '',
        jd_text: `${title} ${company} ${salary}`,
      });
    } catch(e) {}
  }

  // 3. Submit to backend
  const submitResp = await fetch(API_URL + '/admin/jobs/crawl-submit', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ' + access_token,
    },
    body: JSON.stringify({ jobs }),
  });
  const result = await submitResp.json();
  console.log(`✅ 已保存 ${jobs.length} 个岗位到系统`);
  console.log(`   刷新 http://localhost:51668/jobs 查看`);
})();
