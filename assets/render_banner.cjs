const puppeteer = require('puppeteer');
(async () => {
  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 640, deviceScaleFactor: 2 });
  await page.goto('file://' + __dirname + '/banner.html', { waitUntil: 'networkidle0' });
  await page.screenshot({ path: __dirname + '/banner.png', clip: { x: 0, y: 0, width: 1280, height: 640 } });
  await browser.close();
  console.log('wrote banner.png');
})();
