/**
 * 月度 & 年度收益率检测看板 - 数据与渲染
 * 
 * 数据来源：
 * 1. 优先从 fund_data.json 加载（由 fetch_data.py 生成）
 * 2. 如果 JSON 不存在，使用内置示例数据
 * 
 * 计算说明：
 * - 所有对象统一使用: 收益率 = (期末值 - 期初值) / 期初值 × 100%
 * - 美国7-10年国债ETF(IEF) 与其他标的统一口径，均为投资回报率
 * - monthly 中的 null 表示该月无法计算收益率，显示为 "-"
 * - yearly 为 null 表示年度无法计算，显示为 "-"
 * - 负值百分比以红色(#FF5555)显示
 */

// ===================== 状态管理 =====================

let currentYear = new Date().getFullYear();
let allYearData = {};  // { "2025": [...], "2026": [...], ... }
let dataSource = 'fallback';  // 'json' | 'fallback'
let lastUpdated = null;

// ===================== 内置示例数据（fallback）=====================

const FALLBACK_DATA = [
    {
        name: '美国7-10年国债ETF(IEF)',
        code: 'IEF',
        monthly: [1.25, -0.83, 2.14, 0.67, -1.52, 3.08, -0.45, 1.96, -2.13, 0.78, 1.34, -0.62],
        yearly: 5.67
    },
    {
        name: '标普500ETF(SPY)',
        code: 'SPY',
        monthly: [2.08, -1.45, 1.67, -0.92, 2.35, -1.18, 0.84, -0.56, 1.73, -1.04, 2.41, 0.38],
        yearly: 6.31
    },
    {
        name: '上证综合指数',
        code: 'SSE Composite',
        monthly: [0.93, -0.67, 1.82, 1.25, -2.08, 2.74, -0.31, 1.48, -1.76, 0.54, 0.89, -0.43],
        yearly: 4.40
    },
    {
        name: '华夏沪深300ETF联接A',
        code: '000051',
        monthly: [3.15, -2.34, 1.08, -1.67, 3.42, -2.51, 1.93, -0.87, 2.64, -1.38, 3.07, -0.92],
        yearly: 5.60
    },
    {
        name: '南方中证500ETF联接A',
        code: '160119',
        monthly: [2.47, -1.93, 0.86, -2.14, 3.68, -1.75, 2.31, -1.42, 1.95, -0.63, 2.78, -1.08],
        yearly: 4.10
    },
    {
        name: '招商产业债券A',
        code: '217022',
        monthly: [1.74, -2.08, 2.53, -0.45, 1.86, -1.32, 0.97, -1.68, 2.41, -0.89, 1.53, 0.72],
        yearly: 5.34
    },
    {
        name: '安信稳健增值混合A',
        code: '001316',
        monthly: [-0.56, 1.34, -1.87, 2.45, -0.73, 1.68, -2.14, 3.05, -0.98, 1.42, -0.67, 2.13],
        yearly: 5.12
    },
    {
        name: '天弘通利混合A',
        code: '000573',
        monthly: [2.83, -1.56, 3.24, -0.78, 1.45, -2.36, 3.67, -1.23, 2.08, 0.94, -0.45, 1.87],
        yearly: 9.70
    },
    {
        name: '银华中小盘混合',
        code: '180031',
        monthly: [1.67, -0.94, 2.38, -0.53, 1.12, -1.87, 2.95, -0.68, 1.54, 0.73, -0.32, 1.45],
        yearly: 7.50
    },
    {
        name: '贝莱德亚洲猛虎债券A6',
        code: '0P0000VU2Y',
        monthly: [0.85, -0.42, 1.36, 0.94, -0.67, 1.52, -0.28, 0.73, -0.95, 1.18, 0.64, -0.35],
        yearly: 4.55
    },
    {
        name: '普信美国大盘成长A',
        code: '0P00000S71',
        monthly: [2.14, -1.78, 1.93, -1.35, 2.67, -1.46, 1.08, -2.05, 2.83, -0.74, 1.92, 0.53],
        yearly: 5.72
    }
];

// ===================== 数据加载 =====================

/**
 * 从 fund_data.json 加载数据
 */
async function loadDataFromJSON() {
    try {
        const response = await fetch('fund_data.json?t=' + Date.now());
        if (!response.ok) {
            throw new Error('JSON 文件不存在');
        }
        const json = await response.json();
        
        allYearData = json.data;
        lastUpdated = json.updated_at;
        dataSource = 'json';
        
        console.log(`✅ 数据已从 fund_data.json 加载，更新时间: ${lastUpdated}`);
        return true;
    } catch (e) {
        console.warn('⚠️ 无法加载 fund_data.json，使用内置示例数据:', e.message);
        useFallbackData();
        return false;
    }
}

/**
 * 使用内置 fallback 数据
 */
function useFallbackData() {
    // 把 fallback 数据放入 2025 年
    allYearData = { '2025': FALLBACK_DATA };
    dataSource = 'fallback';
    lastUpdated = null;
}

/**
 * 获取当前年份的数据
 */
function getCurrentYearData() {
    const yearStr = String(currentYear);
    if (allYearData[yearStr]) {
        return allYearData[yearStr];
    }
    // 该年份无数据时返回空数组
    return [];
}

// ===================== 渲染逻辑 =====================

/**
 * 渲染表头
 */
function renderTableHead() {
    const thead = document.getElementById('tableHead');
    const tr = document.createElement('tr');

    // 名称列表头
    const thName = document.createElement('th');
    thName.textContent = '名称';
    tr.appendChild(thName);

    // 1-12月列表头
    for (let m = 1; m <= 12; m++) {
        const th = document.createElement('th');
        th.textContent = m + '月';
        tr.appendChild(th);
    }

    // 年度列表头
    const thYear = document.createElement('th');
    thYear.textContent = currentYear.toString();
    thYear.classList.add('year-col');
    tr.appendChild(thYear);

    thead.innerHTML = '';
    thead.appendChild(tr);
}

/**
 * 渲染表格数据行
 */
function renderTableBody() {
    const tbody = document.getElementById('tableBody');
    tbody.innerHTML = '';

    const data = getCurrentYearData();

    if (data.length === 0) {
        // 无数据时显示提示行
        const tr = document.createElement('tr');
        const td = document.createElement('td');
        td.colSpan = 14;
        td.style.textAlign = 'center';
        td.style.padding = '40px';
        td.style.color = '#999';
        td.style.fontSize = '14px';
        td.textContent = `${currentYear}年暂无数据，请运行 fetch_data.py 获取数据`;
        tr.appendChild(td);
        tbody.appendChild(tr);
        return;
    }

    data.forEach((fund) => {
        const tr = document.createElement('tr');

        // 名称单元格
        const tdName = document.createElement('td');
        tdName.innerHTML = `
            <div class="name-cell">
                <span class="name-primary">${fund.name}</span>
                <span class="name-secondary">${fund.code}</span>
            </div>
        `;
        tr.appendChild(tdName);

        // 12个月度收益率
        fund.monthly.forEach((rate) => {
            const td = document.createElement('td');
            if (rate === null || rate === undefined) {
                td.textContent = '-';
                td.classList.add('no-data');
            } else {
                td.textContent = rate.toFixed(2) + '%';
                if (rate < 0) {
                    td.classList.add('negative');
                }
            }
            tr.appendChild(td);
        });

        // 年度累计收益率
        const tdYear = document.createElement('td');
        if (fund.yearly === null || fund.yearly === undefined) {
            tdYear.textContent = '-';
            tdYear.classList.add('no-data');
        } else {
            tdYear.textContent = fund.yearly.toFixed(2) + '%';
            if (fund.yearly < 0) {
                tdYear.classList.add('negative');
            }
        }
        tdYear.classList.add('year-col');
        tr.appendChild(tdYear);

        tbody.appendChild(tr);
    });
}

/**
 * 渲染整个表格
 */
function renderTable() {
    renderTableHead();
    renderTableBody();
}

/**
 * 更新底部信息
 */
function updateFooterInfo() {
    const el = document.getElementById('updateInfo');
    if (!el) return;

    if (dataSource === 'json' && lastUpdated) {
        el.textContent = `数据更新时间: ${lastUpdated}`;
    } else if (dataSource === 'fallback') {
        el.textContent = '* 当前为示例数据，请运行 python fetch_data.py 获取真实数据';
    } else {
        el.textContent = '';
    }
}

// ===================== 更新按钮交互 =====================

/**
 * 显示 toast 提示
 */
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    if (!toast) return;

    toast.textContent = message;
    toast.className = 'toast show';
    if (type === 'success') toast.classList.add('success');
    if (type === 'error') toast.classList.add('error');

    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

/**
 * 手动刷新数据
 */
async function refreshData() {
    const btn = document.getElementById('refreshBtn');
    if (!btn || btn.classList.contains('loading')) return;

    // 进入加载状态
    btn.classList.add('loading');
    btn.classList.remove('success', 'error');
    const textEl = btn.querySelector('.refresh-text');
    const originalText = textEl.textContent;
    textEl.textContent = '更新中...';

    try {
        const loaded = await loadDataFromJSON();

        if (loaded) {
            btn.classList.remove('loading');
            btn.classList.add('success');
            textEl.textContent = '已更新';
            showToast('✅ 数据更新成功', 'success');
        } else {
            btn.classList.remove('loading');
            btn.classList.add('error');
            textEl.textContent = '无数据';
            showToast('⚠️ 未找到 fund_data.json，请先运行 python fetch_data.py', 'error');
        }

        // 刷新数据后重新构建年份选项（可能有新年份）
        buildYearOptions();
        renderTable();
        updateFooterInfo();

    } catch (e) {
        btn.classList.remove('loading');
        btn.classList.add('error');
        textEl.textContent = '失败';
        showToast('❌ 数据更新失败: ' + e.message, 'error');
    }

    // 2秒后恢复按钮状态
    setTimeout(() => {
        btn.classList.remove('success', 'error');
        textEl.textContent = originalText;
    }, 2000);
}

/**
 * 初始化更新按钮
 */
function initRefreshButton() {
    const btn = document.getElementById('refreshBtn');
    if (btn) {
        btn.addEventListener('click', function (e) {
            e.stopPropagation();
            refreshData();
        });
    }
}

// ===================== 年份选择器交互 =====================

/**
 * 根据 allYearData 中的年份动态生成下拉选项
 * 默认选中当前年份（即 new Date().getFullYear()）
 * 当 fund_data.json 中包含某年的数据时，该年份就会出现在下拉列表中
 * 例如：当 fetch_data.py 的 END_YEAR 改为 2027 并重新运行后，2027 就会自动出现
 */
function initYearSelector() {
    const selector = document.getElementById('yearSelector');
    const dropdown = document.getElementById('yearDropdown');
    const yearText = document.getElementById('yearText');

    // 动态生成年份选项
    buildYearOptions();

    // 设置默认显示文本
    yearText.textContent = currentYear + '年';

    // 点击切换下拉
    selector.addEventListener('click', function (e) {
        e.stopPropagation();
        selector.classList.toggle('open');
    });

    // 点击年份选项
    dropdown.addEventListener('click', function (e) {
        const option = e.target.closest('.year-option');
        if (!option) return;

        e.stopPropagation();

        // 更新选中状态
        dropdown.querySelectorAll('.year-option').forEach(opt => opt.classList.remove('active'));
        option.classList.add('active');

        // 更新年份
        currentYear = parseInt(option.dataset.year);
        yearText.textContent = currentYear + '年';

        // 重新渲染表格（表头+表体）
        renderTable();

        // 关闭下拉
        selector.classList.remove('open');
    });

    // 点击外部关闭下拉
    document.addEventListener('click', function () {
        selector.classList.remove('open');
    });
}

/**
 * 根据 allYearData 的 keys 动态构建年份下拉选项
 */
function buildYearOptions() {
    const dropdown = document.getElementById('yearDropdown');
    dropdown.innerHTML = '';

    // 获取所有可用年份并排序（升序）
    const years = Object.keys(allYearData).map(Number).sort((a, b) => a - b);

    // 如果当前年份不在数据中，仍保持 currentYear 不变（表格会显示"暂无数据"）
    // 如果当前年份在数据中，确保它被选中

    years.forEach(year => {
        const div = document.createElement('div');
        div.className = 'year-option';
        if (year === currentYear) {
            div.classList.add('active');
        }
        div.dataset.year = year;
        div.textContent = year + '年';
        dropdown.appendChild(div);
    });
}

// ===================== 初始化 =====================

document.addEventListener('DOMContentLoaded', async function () {
    // 1. 尝试加载 JSON 数据
    await loadDataFromJSON();

    // 2. 渲染表格
    renderTable();

    // 3. 更新底部信息
    updateFooterInfo();

    // 4. 初始化交互
    initYearSelector();
    initRefreshButton();
});
