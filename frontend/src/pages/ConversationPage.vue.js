import { computed, ref } from 'vue';
import { sendChatMessage } from '../api/chat';
import ChatComposer from '../components/ChatComposer.vue';
import ChatMessageCard from '../components/ChatMessageCard.vue';
import ModeSwitch from '../components/ModeSwitch.vue';
import SidebarNav from '../components/SidebarNav.vue';
const currentMode = ref('rag');
const loading = ref(false);
const errorMessage = ref('');
const messages = ref([
    {
        id: 'welcome-assistant',
        role: 'assistant',
        text: '我可以帮你检索知识、分析问题、组织排查步骤。你可以直接发问题，也可以切换回答模式后再发送。',
        timestamp: '10:30',
        status: '演示版工作台已就绪',
    },
]);
const quickQuestions = [
    '支付成功但库存没扣怎么办？',
    '如何定位订单接口的超时问题？',
    '给我总结一下 RAG 和 Direct 的适用区别。',
];
// 作用：在欢迎区展示当前模式对应的简短引导，帮助用户理解这轮提问会怎么走。
const modeSummary = computed(() => {
    if (currentMode.value === 'rag') {
        return '当前更偏向证据型回答，会优先结合知识库内容。';
    }
    if (currentMode.value === 'direct') {
        return '当前更偏向直接作答，不强制依赖检索结果。';
    }
    return '当前会自动判断是否走检索、直答或后续能力链路。';
});
// 作用：把现有消息整理成接口需要的历史格式，便于后续扩展多轮上下文。
function buildHistoryPayload() {
    return messages.value.map((message) => ({
        role: message.role,
        content: message.text,
    }));
}
// 作用：生成消息时间文本，保持消息流的时间展示统一。
function buildTimestamp() {
    return new Date().toLocaleTimeString('zh-CN', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
    });
}
// 作用：往消息列表追加一条用户消息，保证提问会先落在界面上。
function appendUserMessage(question) {
    messages.value.push({
        id: `user-${Date.now()}`,
        role: 'user',
        text: question,
        timestamp: buildTimestamp(),
        mode: currentMode.value,
    });
}
// 作用：把后端返回结果转成助手消息卡片，并附带路由信息和检索证据。
function appendAssistantMessage(payload) {
    const statusText = payload.quality ? `检索质量：${payload.quality}` : '本轮未返回检索质量标记';
    messages.value.push({
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        text: payload.answer,
        timestamp: buildTimestamp(),
        mode: currentMode.value,
        status: statusText,
        routeReason: payload.route_reason,
        sources: payload.retrieval_items,
    });
}
// 作用：统一处理用户发送动作，串联提问、接口调用和结果落卡片。
async function handleSubmit(question) {
    errorMessage.value = '';
    appendUserMessage(question);
    loading.value = true;
    try {
        const payload = await sendChatMessage(question, currentMode.value, buildHistoryPayload());
        appendAssistantMessage(payload);
    }
    catch (error) {
        const message = error instanceof Error ? error.message : '回答生成失败，请稍后重试。';
        errorMessage.value = message;
        messages.value.push({
            id: `assistant-error-${Date.now()}`,
            role: 'assistant',
            text: `这次请求没有成功完成：${message}`,
            timestamp: buildTimestamp(),
            mode: currentMode.value,
            status: '接口调用异常',
        });
    }
    finally {
        loading.value = false;
    }
}
// 作用：让示例问题可以一键带起真实请求，方便本地演示主流程。
function askQuickQuestion(question) {
    void handleSubmit(question);
}
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "app-shell" },
});
/** @type {[typeof SidebarNav, ]} */ ;
// @ts-ignore
const __VLS_0 = __VLS_asFunctionalComponent(SidebarNav, new SidebarNav({}));
const __VLS_1 = __VLS_0({}, ...__VLS_functionalComponentArgsRest(__VLS_0));
__VLS_asFunctionalElement(__VLS_intrinsicElements.main, __VLS_intrinsicElements.main)({
    ...{ class: "workspace-shell" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.header, __VLS_intrinsicElements.header)({
    ...{ class: "hero-panel" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "hero-copy" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "hero-kicker" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
(__VLS_ctx.modeSummary);
/** @type {[typeof ModeSwitch, ]} */ ;
// @ts-ignore
const __VLS_3 = __VLS_asFunctionalComponent(ModeSwitch, new ModeSwitch({
    modelValue: (__VLS_ctx.currentMode),
}));
const __VLS_4 = __VLS_3({
    modelValue: (__VLS_ctx.currentMode),
}, ...__VLS_functionalComponentArgsRest(__VLS_3));
__VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
    ...{ class: "quick-question-row" },
});
for (const [question] of __VLS_getVForSourceType((__VLS_ctx.quickQuestions))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                __VLS_ctx.askQuickQuestion(question);
            } },
        key: (question),
        type: "button",
        ...{ class: "quick-question" },
    });
    (question);
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
    ...{ class: "chat-panel" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "chat-panel-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "section-caption" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "chat-panel-status" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "online-dot" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
(__VLS_ctx.loading ? '正在生成回答' : '接口已连接');
if (__VLS_ctx.errorMessage) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "error-banner" },
    });
    (__VLS_ctx.errorMessage);
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "chat-message-list" },
});
for (const [message] of __VLS_getVForSourceType((__VLS_ctx.messages))) {
    /** @type {[typeof ChatMessageCard, ]} */ ;
    // @ts-ignore
    const __VLS_6 = __VLS_asFunctionalComponent(ChatMessageCard, new ChatMessageCard({
        key: (message.id),
        message: (message),
    }));
    const __VLS_7 = __VLS_6({
        key: (message.id),
        message: (message),
    }, ...__VLS_functionalComponentArgsRest(__VLS_6));
}
/** @type {[typeof ChatComposer, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(ChatComposer, new ChatComposer({
    ...{ 'onSubmit': {} },
    loading: (__VLS_ctx.loading),
}));
const __VLS_10 = __VLS_9({
    ...{ 'onSubmit': {} },
    loading: (__VLS_ctx.loading),
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
let __VLS_12;
let __VLS_13;
let __VLS_14;
const __VLS_15 = {
    onSubmit: (__VLS_ctx.handleSubmit)
};
var __VLS_11;
/** @type {__VLS_StyleScopedClasses['app-shell']} */ ;
/** @type {__VLS_StyleScopedClasses['workspace-shell']} */ ;
/** @type {__VLS_StyleScopedClasses['hero-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['hero-copy']} */ ;
/** @type {__VLS_StyleScopedClasses['hero-kicker']} */ ;
/** @type {__VLS_StyleScopedClasses['quick-question-row']} */ ;
/** @type {__VLS_StyleScopedClasses['quick-question']} */ ;
/** @type {__VLS_StyleScopedClasses['chat-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['chat-panel-header']} */ ;
/** @type {__VLS_StyleScopedClasses['section-caption']} */ ;
/** @type {__VLS_StyleScopedClasses['chat-panel-status']} */ ;
/** @type {__VLS_StyleScopedClasses['online-dot']} */ ;
/** @type {__VLS_StyleScopedClasses['error-banner']} */ ;
/** @type {__VLS_StyleScopedClasses['chat-message-list']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            ChatComposer: ChatComposer,
            ChatMessageCard: ChatMessageCard,
            ModeSwitch: ModeSwitch,
            SidebarNav: SidebarNav,
            currentMode: currentMode,
            loading: loading,
            errorMessage: errorMessage,
            messages: messages,
            quickQuestions: quickQuestions,
            modeSummary: modeSummary,
            handleSubmit: handleSubmit,
            askQuickQuestion: askQuickQuestion,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
