import SourceList from './SourceList.vue';
const __VLS_props = defineProps();
// 作用：把不同消息角色映射成更容易识别的显示名称。
function roleLabel(role) {
    return role === 'user' ? '你' : '助手';
}
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
__VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
    ...{ class: "chat-card" },
    ...{ class: ([`is-${__VLS_ctx.message.role}`]) },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "chat-card-avatar" },
});
(__VLS_ctx.message.role === 'user' ? '你' : '智');
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "chat-card-body" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "chat-card-meta" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "chat-card-role" },
});
(__VLS_ctx.roleLabel(__VLS_ctx.message.role));
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "chat-card-time" },
});
(__VLS_ctx.message.timestamp);
if (__VLS_ctx.message.mode) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "chat-card-badge" },
    });
    (__VLS_ctx.message.mode.toUpperCase());
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "chat-card-text" },
});
(__VLS_ctx.message.text);
if (__VLS_ctx.message.status || __VLS_ctx.message.routeReason) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "chat-card-status" },
    });
    if (__VLS_ctx.message.status) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        (__VLS_ctx.message.status);
    }
    if (__VLS_ctx.message.routeReason) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        (__VLS_ctx.message.routeReason);
    }
}
if (__VLS_ctx.message.sources?.length) {
    /** @type {[typeof SourceList, ]} */ ;
    // @ts-ignore
    const __VLS_0 = __VLS_asFunctionalComponent(SourceList, new SourceList({
        items: (__VLS_ctx.message.sources),
    }));
    const __VLS_1 = __VLS_0({
        items: (__VLS_ctx.message.sources),
    }, ...__VLS_functionalComponentArgsRest(__VLS_0));
}
/** @type {__VLS_StyleScopedClasses['chat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['chat-card-avatar']} */ ;
/** @type {__VLS_StyleScopedClasses['chat-card-body']} */ ;
/** @type {__VLS_StyleScopedClasses['chat-card-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['chat-card-role']} */ ;
/** @type {__VLS_StyleScopedClasses['chat-card-time']} */ ;
/** @type {__VLS_StyleScopedClasses['chat-card-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['chat-card-text']} */ ;
/** @type {__VLS_StyleScopedClasses['chat-card-status']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            SourceList: SourceList,
            roleLabel: roleLabel,
        };
    },
    __typeProps: {},
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
    __typeProps: {},
});
; /* PartiallyEnd: #4569/main.vue */
