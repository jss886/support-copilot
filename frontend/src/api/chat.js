// 作用：调用后端聊天接口，统一返回前端工作台渲染所需的结构。
export async function sendChatMessage(question, mode, history) {
    const response = await fetch('/api/v1/chat/respond', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            question,
            mode,
            messages: history,
        }),
    });
    const payload = (await response.json());
    if (!response.ok || !payload.success) {
        throw new Error(payload.message || '聊天接口调用失败。');
    }
    return payload.data;
}
