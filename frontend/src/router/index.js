import { createRouter, createWebHistory } from 'vue-router';
import ConversationPage from '../pages/ConversationPage.vue';
import PlaceholderPage from '../pages/PlaceholderPage.vue';
const router = createRouter({
    history: createWebHistory(),
    routes: [
        {
            path: '/',
            redirect: '/conversation',
        },
        {
            path: '/conversation',
            component: ConversationPage,
            meta: {
                title: '对话',
            },
        },
        {
            path: '/knowledge',
            component: PlaceholderPage,
            props: {
                title: '知识库',
                description: '这里后面接知识库导入、文档列表和来源过滤。',
            },
            meta: {
                title: '知识库',
            },
        },
        {
            path: '/memory',
            component: PlaceholderPage,
            props: {
                title: '任务记忆',
                description: '这里后面接任务记忆沉淀和可复用经验卡片。',
            },
            meta: {
                title: '任务记忆',
            },
        },
        {
            path: '/agents',
            component: PlaceholderPage,
            props: {
                title: '智能体',
                description: '这里后面接多 Agent 路由、工具和执行状态展示。',
            },
            meta: {
                title: '智能体',
            },
        },
        {
            path: '/settings',
            component: PlaceholderPage,
            props: {
                title: '设置',
                description: '这里后面接模型、知识源和界面开关等配置。',
            },
            meta: {
                title: '设置',
            },
        },
    ],
});
// 作用：在切换页面时同步更新浏览器标题，方便本地演示时区分当前页面。
router.afterEach((to) => {
    const title = typeof to.meta.title === 'string' ? to.meta.title : '研发知识助手';
    document.title = `${title} - 研发知识助手`;
});
export default router;
