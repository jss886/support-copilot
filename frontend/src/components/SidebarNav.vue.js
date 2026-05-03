import { computed } from 'vue';
import { RouterLink, useRoute } from 'vue-router';
const route = useRoute();
const navItems = [
    { label: '对话', to: '/conversation', icon: '◌' },
    { label: '知识库', to: '/knowledge', icon: '◍' },
    { label: '任务记忆', to: '/memory', icon: '⌘' },
    { label: '智能体', to: '/agents', icon: '✦' },
    { label: '设置', to: '/settings', icon: '⚙' },
];
// 作用：根据当前路由高亮左侧导航项，保持工作台结构稳定。
function isActive(path) {
    return route.path === path;
}
const adminLabel = computed(() => 'Admin');
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
__VLS_asFunctionalElement(__VLS_intrinsicElements.aside, __VLS_intrinsicElements.aside)({
    ...{ class: "sidebar-shell" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "sidebar-brand" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "sidebar-brand-mark" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "brand-orb brand-orb-left" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "brand-orb brand-orb-right" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "sidebar-brand-title" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "sidebar-brand-subtitle" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ class: "new-chat-button" },
    type: "button",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.nav, __VLS_intrinsicElements.nav)({
    ...{ class: "sidebar-nav" },
});
for (const [item] of __VLS_getVForSourceType((__VLS_ctx.navItems))) {
    const __VLS_0 = {}.RouterLink;
    /** @type {[typeof __VLS_components.RouterLink, typeof __VLS_components.RouterLink, ]} */ ;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
        key: (item.to),
        to: (item.to),
        ...{ class: "sidebar-nav-item" },
        ...{ class: ({ 'is-active': __VLS_ctx.isActive(item.to) }) },
    }));
    const __VLS_2 = __VLS_1({
        key: (item.to),
        to: (item.to),
        ...{ class: "sidebar-nav-item" },
        ...{ class: ({ 'is-active': __VLS_ctx.isActive(item.to) }) },
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    __VLS_3.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "sidebar-nav-icon" },
    });
    (item.icon);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    (item.label);
    var __VLS_3;
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "sidebar-admin" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "sidebar-admin-avatar" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "sidebar-admin-name" },
});
(__VLS_ctx.adminLabel);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "sidebar-admin-status" },
});
/** @type {__VLS_StyleScopedClasses['sidebar-shell']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar-brand']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar-brand-mark']} */ ;
/** @type {__VLS_StyleScopedClasses['brand-orb']} */ ;
/** @type {__VLS_StyleScopedClasses['brand-orb-left']} */ ;
/** @type {__VLS_StyleScopedClasses['brand-orb']} */ ;
/** @type {__VLS_StyleScopedClasses['brand-orb-right']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar-brand-title']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar-brand-subtitle']} */ ;
/** @type {__VLS_StyleScopedClasses['new-chat-button']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar-nav']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar-nav-item']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar-nav-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar-admin']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar-admin-avatar']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar-admin-name']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar-admin-status']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            RouterLink: RouterLink,
            navItems: navItems,
            isActive: isActive,
            adminLabel: adminLabel,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
