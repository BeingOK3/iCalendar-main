/**
 * iCalendar Web Client - JavaScript 应用逻辑
 * 
 * 主要功能：
 * - 日历渲染和交互
 * - 自然语言处理
 * - 事件CRUD操作
 * - 实时更新
 */

// ========== 全局变量 ==========
let calendar = null;
let calendars = [];
let currentEvent = null;
const API_BASE = window.location.origin;
let isSending = false; // 发送状态标志

// ========== 初始化 ==========
document.addEventListener('DOMContentLoaded', async function() {
    console.log('Initializing iCalendar Web Client...');
    
    // 初始化日历
    initCalendar();
    
    // 加载日历列表
    await loadCalendars();
    
    // 加载事件
    await loadEvents();
    
    // 绑定事件监听器
    bindEventListeners();
    
    console.log('Initialization complete!');
});

// ========== 日历初始化 ==========
function initCalendar() {
    const calendarEl = document.getElementById('calendar');
    
    calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',
        headerToolbar: {
            left: 'prev,next today',
            center: 'title',
            right: 'dayGridMonth,timeGridWeek,timeGridDay,listWeek'
        },
        locale: 'zh-cn',
        buttonText: {
            today: '今天',
            month: '月',
            week: '周',
            day: '日',
            list: '列表'
        },
        firstDay: 1, // 周一作为一周的开始
        navLinks: true,
        editable: true,
        selectable: true,
        selectMirror: true,
        dayMaxEvents: true,
        
        // 点击日期创建事件
        select: function(info) {
            showCreateEventModal(info.start, info.end);
        },
        
        // 点击事件查看/编辑
        eventClick: function(info) {
            showEditEventModal(info.event);
        },
        
        // 拖拽事件更新时间
        eventDrop: async function(info) {
            await updateEventTime(info.event, info.event.start, info.event.end);
        },
        
        // 调整事件时长
        eventResize: async function(info) {
            await updateEventTime(info.event, info.event.start, info.event.end);
        }
    });
    
    calendar.render();
}

// ========== 加载数据 ==========
async function loadCalendars() {
    try {
        const response = await fetch(`${API_BASE}/api/calendars`);
        if (!response.ok) throw new Error('Failed to load calendars');
        
        calendars = await response.json();
        
        // 更新日历选择器
        updateCalendarSelectors();
        
        console.log('Loaded calendars:', calendars);
    } catch (error) {
        console.error('Error loading calendars:', error);
        showToast('加载日历列表失败', 'error');
    }
}

async function loadEvents(startDate = null, endDate = null, calendarName = null) {
    try {
        showLoading(true);
        
        // 构建查询参数
        const params = new URLSearchParams();
        if (startDate) params.append('start_date', startDate);
        if (endDate) params.append('end_date', endDate);
        if (calendarName) params.append('calendar_name', calendarName);
        
        const response = await fetch(`${API_BASE}/api/events?${params}`);
        if (!response.ok) throw new Error('Failed to load events');
        
        const data = await response.json();
        
        // 清除现有事件
        calendar.removeAllEvents();
        
        // 添加新事件
        if (data.events && data.events.length > 0) {
            data.events.forEach(event => {
                calendar.addEvent({
                    id: event.id,
                    title: event.title,
                    start: event.start_time,
                    end: event.end_time,
                    extendedProps: {
                        location: event.location,
                        description: event.description,
                        calendar_name: event.calendar_name
                    },
                    backgroundColor: getCalendarColor(event.calendar_name)
                });
            });
        }
        
        console.log(`Loaded ${data.count} events`);
        showLoading(false);
    } catch (error) {
        console.error('Error loading events:', error);
        showToast('加载事件失败', 'error');
        showLoading(false);
    }
}

// ========== 聊天功能 ==========
async function processNaturalLanguage(text) {
    // 检查是否正在发送中
    if (isSending) {
        console.log('Already sending, please wait...');
        return null;
    }
    
    try {
        // 设置发送状态
        isSending = true;
        updateSendButtonState();
        
        // 添加用户消息到聊天界面
        addMessage(text, 'user');
        
        // 显示加载动画
        showTypingIndicator();
        
        const response = await fetch(`${API_BASE}/api/nl/execute`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ text })
        });
        
        if (!response.ok) throw new Error('Failed to process natural language');
        
        const result = await response.json();
        
        // 移除加载动画
        hideTypingIndicator();
        
        // 添加AI响应到聊天界面
        let message = result.response || result.message || '操作完成';
        
        // 如果返回了事件列表，格式化显示
        if (result.data && result.data.events && result.data.events.length > 0) {
            message += '\n\n';
            result.data.events.forEach((event, index) => {
                const startTime = event.start_time ? new Date(event.start_time).toLocaleString('zh-CN', {
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit'
                }) : '时间未知';
                message += `\n${index + 1}. ${event.title} (${startTime})`;
            });
        }
        
        addMessage(message, 'ai');
        
        // 如果操作成功，重新加载事件
        if (result.success) {
            await loadEvents();
        }
        
        return result;
    } catch (error) {
        console.error('Error processing natural language:', error);
        hideTypingIndicator();
        addMessage('抱歉，处理您的请求时出现错误。', 'ai');
        return null;
    } finally {
        // 恢复发送状态
        isSending = false;
        updateSendButtonState();
    }
}

function addMessage(text, type) {
    const chatMessages = document.getElementById('chatMessages');
    
    // 移除欢迎消息（如果存在）
    const welcomeMsg = document.querySelector('.welcome-message');
    if (welcomeMsg) {
        welcomeMsg.remove();
    }
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message message-${type}`;
    
    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.innerHTML = type === 'user' ? '<i class="fas fa-user"></i>' : '<i class="fas fa-robot"></i>';
    
    const content = document.createElement('div');
    content.className = 'message-content';
    
    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    bubble.textContent = text;
    
    const time = document.createElement('div');
    time.className = 'message-time';
    time.textContent = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    
    content.appendChild(bubble);
    content.appendChild(time);
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(content);
    chatMessages.appendChild(messageDiv);
    
    // 滚动到最新消息
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function showTypingIndicator() {
    const chatMessages = document.getElementById('chatMessages');
    
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'message-loading';
    loadingDiv.id = 'typingIndicator';
    
    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.innerHTML = '<i class="fas fa-robot"></i>';
    avatar.style.background = 'var(--light-bg)';
    avatar.style.color = 'var(--primary-color)';
    
    const content = document.createElement('div');
    content.className = 'message-content';
    
    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    bubble.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';
    
    content.appendChild(bubble);
    loadingDiv.appendChild(avatar);
    loadingDiv.appendChild(content);
    chatMessages.appendChild(loadingDiv);
    
    // 滚动到最新消息
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function hideTypingIndicator() {
    const indicator = document.getElementById('typingIndicator');
    if (indicator) {
        indicator.remove();
    }
}

// 更新发送按钮状态
function updateSendButtonState() {
    const sendBtn = document.getElementById('sendBtn');
    const chatInput = document.getElementById('chatInput');
    
    if (isSending) {
        sendBtn.disabled = true;
        sendBtn.style.opacity = '0.5';
        sendBtn.style.cursor = 'not-allowed';
        chatInput.disabled = true;
        chatInput.style.opacity = '0.7';
    } else {
        sendBtn.disabled = false;
        sendBtn.style.opacity = '1';
        sendBtn.style.cursor = 'pointer';
        chatInput.disabled = false;
        chatInput.style.opacity = '1';
    }
}

async function clearChat() {
    // ========== 清除前端显示的聊天记录 ==========
    const chatMessages = document.getElementById('chatMessages');
    chatMessages.innerHTML = `
        <div class="welcome-message">
            <i class="fas fa-robot"></i>
            <p>您好！我是智能助手，可以帮您管理日程。</p>
            <div class="quick-examples">
                <p>试试这些操作：</p>
                <button class="example-btn" onclick="sendExample('明天下午3点开会')">明天下午3点开会</button>
                <button class="example-btn" onclick="sendExample('查看本周的日程')">查看本周的日程</button>
                <button class="example-btn" onclick="sendExample('删除今天的会议')">删除今天的会议</button>
            </div>
        </div>
    `;
    
    // ========== 清除服务器端的对话历史（支持上下文记忆）==========
    try {
        await fetch(`${API_BASE}/api/conversation/clear?session_id=default`, {
            method: 'DELETE'
        });
        console.log('Server conversation history cleared');
    } catch (error) {
        console.error('Error clearing server conversation history:', error);
    }
}

function sendExample(text) {
    document.getElementById('chatInput').value = text;
    document.getElementById('sendBtn').click();
}

// ========== 事件CRUD操作 ==========
async function createEvent(eventData) {
    try {
        showLoading(true);
        
        const response = await fetch(`${API_BASE}/api/events`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(eventData)
        });
        
        if (!response.ok) throw new Error('Failed to create event');
        
        const result = await response.json();
        
        showLoading(false);
        showToast(result.message || '事件创建成功', 'success');
        
        // 重新加载事件
        await loadEvents();
        
        return result;
    } catch (error) {
        console.error('Error creating event:', error);
        showToast('创建事件失败', 'error');
        showLoading(false);
        return null;
    }
}

async function updateEvent(eventId, updateData) {
    try {
        showLoading(true);
        
        const response = await fetch(`${API_BASE}/api/events/${eventId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(updateData)
        });
        
        if (!response.ok) throw new Error('Failed to update event');
        
        const result = await response.json();
        
        showLoading(false);
        showToast(result.message || '事件更新成功', 'success');
        
        // 重新加载事件
        await loadEvents();
        
        return result;
    } catch (error) {
        console.error('Error updating event:', error);
        showToast('更新事件失败', 'error');
        showLoading(false);
        return null;
    }
}

async function deleteEvent() {
    if (!currentEvent) return;
    
    if (!confirm('确定要删除这个事件吗？')) {
        return;
    }
    
    try {
        showLoading(true);
        
        const eventId = currentEvent.id;
        const response = await fetch(`${API_BASE}/api/events/${eventId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) throw new Error('Failed to delete event');
        
        const result = await response.json();
        
        showLoading(false);
        showToast(result.message || '事件删除成功', 'success');
        
        // 关闭模态框
        closeEventModal();
        
        // 重新加载事件
        await loadEvents();
    } catch (error) {
        console.error('Error deleting event:', error);
        showToast('删除事件失败', 'error');
        showLoading(false);
    }
}

async function updateEventTime(event, newStart, newEnd) {
    try {
        const updateData = {
            start_time: newStart.toISOString(),
            end_time: newEnd ? newEnd.toISOString() : null
        };
        
        await updateEvent(event.id, updateData);
    } catch (error) {
        console.error('Error updating event time:', error);
        // 回滚更改
        event.revert();
    }
}

// ========== 模态框操作 ==========
function showCreateEventModal(start, end = null) {
    currentEvent = null;
    
    document.getElementById('modalTitle').textContent = '创建新事件';
    document.getElementById('eventId').value = '';
    document.getElementById('eventTitle').value = '';
    document.getElementById('eventStartTime').value = formatDateTimeLocal(start);
    document.getElementById('eventEndTime').value = end ? formatDateTimeLocal(end) : '';
    document.getElementById('eventLocation').value = '';
    document.getElementById('eventDescription').value = '';
    document.getElementById('eventCalendar').value = '';
    
    // 隐藏删除按钮
    document.getElementById('deleteEventBtn').style.display = 'none';
    
    showModal();
}

function showEditEventModal(event) {
    currentEvent = event;
    
    document.getElementById('modalTitle').textContent = '编辑事件';
    document.getElementById('eventId').value = event.id;
    document.getElementById('eventTitle').value = event.title;
    document.getElementById('eventStartTime').value = formatDateTimeLocal(event.start);
    document.getElementById('eventEndTime').value = event.end ? formatDateTimeLocal(event.end) : '';
    document.getElementById('eventLocation').value = event.extendedProps.location || '';
    document.getElementById('eventDescription').value = event.extendedProps.description || '';
    document.getElementById('eventCalendar').value = event.extendedProps.calendar_name || '';
    
    // 显示删除按钮
    document.getElementById('deleteEventBtn').style.display = 'block';
    
    showModal();
}

function showModal() {
    document.getElementById('eventModal').classList.add('show');
}

function closeEventModal() {
    document.getElementById('eventModal').classList.remove('show');
    currentEvent = null;
}

// ========== UI辅助函数 ==========
function showLoading(show) {
    const overlay = document.getElementById('loadingOverlay');
    overlay.style.display = show ? 'flex' : 'none';
}

function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type} show`;
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}



function updateCalendarSelectors() {
    const selectors = [
        document.getElementById('calendarSelect'),
        document.getElementById('eventCalendar')
    ];
    
    selectors.forEach(select => {
        if (!select) return;
        
        // 保存当前选中的值
        const currentValue = select.value;
        
        // 清空选项
        select.innerHTML = '';
        
        // 添加默认选项（仅对筛选器）
        if (select.id === 'calendarSelect') {
            const defaultOption = document.createElement('option');
            defaultOption.value = '';
            defaultOption.textContent = '所有日历';
            select.appendChild(defaultOption);
        }
        
        // 添加日历选项
        calendars.forEach(cal => {
            const option = document.createElement('option');
            option.value = cal;
            option.textContent = cal;
            select.appendChild(option);
        });
        
        // 恢复选中的值
        select.value = currentValue;
    });
}

function getCalendarColor(calendarName) {
    // 为不同日历分配不同颜色
    const colors = [
        '#4A90E2', '#E24A90', '#90E24A', '#E2904A',
        '#4AE290', '#904AE2', '#E2E24A', '#4A4AE2'
    ];
    
    if (!calendarName) return colors[0];
    
    const index = calendars.indexOf(calendarName);
    return colors[index % colors.length];
}

function formatDateTimeLocal(date) {
    if (!(date instanceof Date)) {
        date = new Date(date);
    }
    
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    
    return `${year}-${month}-${day}T${hours}:${minutes}`;
}

// ========== 事件监听器 ==========
function bindEventListeners() {
    // 聊天输入提交
    document.getElementById('sendBtn').addEventListener('click', async () => {
        // 如果正在发送中，忽略点击
        if (isSending) {
            console.log('请等待上一条消息处理完成');
            return;
        }
        
        const input = document.getElementById('chatInput');
        const text = input.value.trim();
        
        if (!text) {
            return;
        }
        
        await processNaturalLanguage(text);
        input.value = ''; // 清空输入框
        input.style.height = 'auto'; // 重置高度
    });
    
    // 回车提交（Shift+Enter 换行）
    document.getElementById('chatInput').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            // 如果正在发送中，忽略回车键
            if (!isSending) {
                document.getElementById('sendBtn').click();
            }
        }
    });
    
    // 自动调整输入框高度
    document.getElementById('chatInput').addEventListener('input', (e) => {
        e.target.style.height = 'auto';
        e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
    });
    
    // 清除聊天记录
    document.getElementById('clearChatBtn').addEventListener('click', () => {
        if (confirm('确定要清除所有聊天记录吗？')) {
            clearChat();
        }
    });
    
    // 刷新按钮
    document.getElementById('refreshBtn').addEventListener('click', async () => {
        await loadEvents();
        showToast('已刷新', 'success');
    });
    
    // 日历筛选
    document.getElementById('calendarSelect').addEventListener('change', async (e) => {
        const calendarName = e.target.value || null;
        await loadEvents(null, null, calendarName);
    });
    
    // 事件表单提交
    document.getElementById('eventForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const eventId = document.getElementById('eventId').value;
        const title = document.getElementById('eventTitle').value;
        const startTime = document.getElementById('eventStartTime').value;
        const endTime = document.getElementById('eventEndTime').value;
        const location = document.getElementById('eventLocation').value;
        const description = document.getElementById('eventDescription').value;
        const calendarName = document.getElementById('eventCalendar').value;
        
        const eventData = {
            title,
            start_time: new Date(startTime).toISOString(),
            end_time: endTime ? new Date(endTime).toISOString() : null,
            location: location || null,
            description: description || null,
            calendar_name: calendarName || null
        };
        
        if (eventId) {
            // 更新事件
            await updateEvent(eventId, eventData);
        } else {
            // 创建事件
            await createEvent(eventData);
        }
        
        closeEventModal();
    });
    
    // 点击模态框外部关闭
    document.getElementById('eventModal').addEventListener('click', (e) => {
        if (e.target.id === 'eventModal') {
            closeEventModal();
        }
    });
}

// ========== 导出函数供HTML使用 ==========
window.sendExample = sendExample;
window.clearChat = clearChat;
window.showCreateEventModal = showCreateEventModal;
window.closeEventModal = closeEventModal;
window.deleteEvent = deleteEvent;
