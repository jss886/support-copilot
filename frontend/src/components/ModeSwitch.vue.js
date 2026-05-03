const props = defineProps();
const emit = defineEmits();
const modeCards = [
    {
        key: 'rag',
        title: 'RAG',
        description: '基于知识库检索，给出更稳的证据型回答。',
        icon: '◍',
    },
    {
        key: 'direct',
        title: 'Direct',
        description: '直接作答，不强依赖知识库，适合常识或泛化问题。',
        icon: '⚡',
    },
    {
        key: 'auto',
        title: 'Auto',
        description: '自动判断是否走检索、直答或后续工具链路。',
        icon: '✦',
    },
];
// 作用：把用户点击的模式同步给父组件，统一驱动当前聊天策略。
function selectMode(mode) {
    emit('update:modelValue', mode);
}
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
__VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
    ...{ class: "mode-switch" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "section-caption" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "mode-switch-grid" },
});
for (const [mode] of __VLS_getVForSourceType((__VLS_ctx.modeCards))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                __VLS_ctx.selectMode(mode.key);
            } },
        key: (mode.key),
        type: "button",
        ...{ class: "mode-card" },
        ...{ class: ({ 'is-active': props.modelValue === mode.key }) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mode-card-title" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "mode-card-icon" },
    });
    (mode.icon);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    (mode.title);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mode-card-description" },
    });
    (mode.description);
}
/** @type {__VLS_StyleScopedClasses['mode-switch']} */ ;
/** @type {__VLS_StyleScopedClasses['section-caption']} */ ;
/** @type {__VLS_StyleScopedClasses['mode-switch-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['mode-card']} */ ;
/** @type {__VLS_StyleScopedClasses['mode-card-title']} */ ;
/** @type {__VLS_StyleScopedClasses['mode-card-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['mode-card-description']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            modeCards: modeCards,
            selectMode: selectMode,
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
