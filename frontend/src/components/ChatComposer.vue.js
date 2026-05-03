import { ref, watch } from 'vue';
const props = defineProps();
const emit = defineEmits();
const draft = ref('支付成功但库存没扣怎么办？');
watch(() => props.loading, (loading) => {
    if (!loading) {
        draft.value = '';
    }
});
// 作用：在输入内容有效时提交问题，避免前端发送空消息。
function submitQuestion() {
    const value = draft.value.trim();
    if (!value || props.loading) {
        return;
    }
    emit('submit', value);
}
// 作用：让输入框支持回车发送，提升聊天场景下的交互效率。
function handleKeydown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        submitQuestion();
    }
}
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
__VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
    ...{ class: "composer-shell" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.textarea, __VLS_intrinsicElements.textarea)({
    ...{ onKeydown: (__VLS_ctx.handleKeydown) },
    value: (__VLS_ctx.draft),
    ...{ class: "composer-input" },
    disabled: (__VLS_ctx.loading),
    placeholder: "输入你的问题，助手会结合模式给出回答...",
    rows: "3",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "composer-toolbar" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "composer-tools" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    type: "button",
    ...{ class: "tool-button" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    type: "button",
    ...{ class: "tool-button" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    type: "button",
    ...{ class: "tool-button" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.submitQuestion) },
    type: "button",
    ...{ class: "send-button" },
    disabled: (__VLS_ctx.loading),
});
(__VLS_ctx.loading ? '回答中...' : '发送');
/** @type {__VLS_StyleScopedClasses['composer-shell']} */ ;
/** @type {__VLS_StyleScopedClasses['composer-input']} */ ;
/** @type {__VLS_StyleScopedClasses['composer-toolbar']} */ ;
/** @type {__VLS_StyleScopedClasses['composer-tools']} */ ;
/** @type {__VLS_StyleScopedClasses['tool-button']} */ ;
/** @type {__VLS_StyleScopedClasses['tool-button']} */ ;
/** @type {__VLS_StyleScopedClasses['tool-button']} */ ;
/** @type {__VLS_StyleScopedClasses['send-button']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            draft: draft,
            submitQuestion: submitQuestion,
            handleKeydown: handleKeydown,
        };
    },
    __typeEmits: {},
    __typeProps: {},
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
    __typeEmits: {},
    __typeProps: {},
});
; /* PartiallyEnd: #4569/main.vue */
