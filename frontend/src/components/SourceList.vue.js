const __VLS_props = defineProps();
// 作用：把过长的来源路径压缩成更适合卡片展示的短标签。
function formatSource(source) {
    const parts = source.split(/[\\/]/).filter(Boolean);
    return parts.slice(-2).join(' / ') || source;
}
// 作用：把检索分数转成更直观的百分比，方便演示时快速判断证据强弱。
function formatScore(score) {
    return `${Math.max(0, Math.min(100, Math.round(score * 100)))}%`;
}
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
if (__VLS_ctx.items.length) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "source-list" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "source-list-header" },
    });
    for (const [item, index] of __VLS_getVForSourceType((__VLS_ctx.items))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
            key: (`${item.source}-${index}`),
            ...{ class: "source-item" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "source-item-topline" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "source-item-name" },
        });
        (__VLS_ctx.formatSource(item.source));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "source-item-score" },
        });
        (__VLS_ctx.formatScore(item.score));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
            ...{ class: "source-item-text" },
        });
        (item.text);
    }
}
/** @type {__VLS_StyleScopedClasses['source-list']} */ ;
/** @type {__VLS_StyleScopedClasses['source-list-header']} */ ;
/** @type {__VLS_StyleScopedClasses['source-item']} */ ;
/** @type {__VLS_StyleScopedClasses['source-item-topline']} */ ;
/** @type {__VLS_StyleScopedClasses['source-item-name']} */ ;
/** @type {__VLS_StyleScopedClasses['source-item-score']} */ ;
/** @type {__VLS_StyleScopedClasses['source-item-text']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            formatSource: formatSource,
            formatScore: formatScore,
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
