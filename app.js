// 海龟汤游戏主逻辑 - 对话模式
document.addEventListener('DOMContentLoaded', function() {
    const chatContainer = document.getElementById('puzzle-display');
    const userInput = document.getElementById('user-guess');
    const submitBtn = document.getElementById('submit-guess');
    const newPuzzleBtn = document.getElementById('new-puzzle');
    const getHintBtn = document.getElementById('get-hint');
    const solveBtn = document.getElementById('solve');
    
    let currentPuzzle = null;
    let currentPuzzleFile = null;
    let cluesGiven = [];
    
    // 新谜题按钮
    newPuzzleBtn.addEventListener('click', loadRandomPuzzle);
    
    // 获取提示按钮
    getHintBtn.addEventListener('click', async () => {
        if (!currentPuzzle) return;
        
        // 显示等待状态
        const waitingSpan = addMessage('获取提示中...', 'bot');
        // 锁定UI
        lockUI();
        
        try {
            const response = await callOpenRouterAPI([
                { role: "system", content: `你是一个海龟汤游戏主持人，根据以下谜题提供一个不泄露谜底的提示：
谜题: ${currentPuzzle}
规则:
1. 提示应该引导思考但不要直接给出答案
2. 提示应该简短明了` },
                { role: "user", content: "请给我一个提示" }
            ]);
            
            // 替换等待消息为实际提示
            const container = document.createElement('div');
            container.className = 'message-container';
            
            const responseSpan = document.createElement('span');
            responseSpan.className = 'bot-message';
            responseSpan.textContent = response;
            container.appendChild(responseSpan);
            
            waitingSpan.parentNode.replaceChild(container, waitingSpan);
        } catch (error) {
            // 替换等待消息为错误信息
            addMessage(`获取提示失败: ${error.message}`, 'error', waitingSpan.id);
        } finally {
            // 解锁UI
            unlockUI();
        }
    });
    
    // 解答按钮
    solveBtn.addEventListener('click', () => {
        if (!currentPuzzle) return;
        
        const solutionMatch = currentPuzzle.match(/### 汤底([\s\S]*?)(###|$)/);
        if (solutionMatch) {
            addMessage('谜底：' + solutionMatch[1].trim(), 'bot');
        }
    });

    // 锁定UI
    function lockUI() {
        userInput.disabled = true;
        submitBtn.disabled = true;
        userInput.placeholder = "处理中...";
    }

    // 解锁UI
    function unlockUI() {
        userInput.disabled = false;
        submitBtn.disabled = false;
        userInput.placeholder = "输入你的猜测...";
        userInput.focus();
    }
    
    // 加载随机谜题
    loadRandomPuzzle();
    
    async function loadRandomPuzzle() {
        try {
            const puzzleFiles = [
                '100元钱.md', '保龄球.md', '免费的大餐.md', '关灯之后.md',
                '最棒的一天.md', '对赌.md', '延迟死亡.md', '忠诚的狗.md',
                '怀孕.md', '手滑.md', '挑衅.md', '捉迷藏.md', '捉迷藏2.md',
                '接连死去的哥哥.md', '日访三十国.md', '杀人早餐.md',
                '杀妻后自杀.md', '死亡直播.md', '水池中的死者.md', '治病.md',
                '爱犬.md', '生意.md', '电梯里的人.md', '看病.md',
                '看起来没那么严重.md', '祭日.md', '私人医生.md', '脚步声.md',
                '自相残杀.md', '街上的工作.md', '裤子破了.md', '要好的朋友.md',
                '要水拿枪.md', '车头灯关闭.md', '长路终有归途.md'
            ];
            
            const randomFile = puzzleFiles[Math.floor(Math.random() * puzzleFiles.length)];
            const response = await fetch(`puzzles/${randomFile}`);
            currentPuzzle = await response.text();
            
            const puzzleMatch = currentPuzzle.match(/### 汤面([\s\S]*?)### 汤底/);
            const puzzleText = puzzleMatch ? puzzleMatch[1].trim() : currentPuzzle.split('### 汤底')[0].trim();
            const puzzleName = randomFile.replace('.md', '');
            
            // 清空容器
            chatContainer.innerHTML = '';
            
            // 添加谜题标题和内容
            const puzzleDiv = document.createElement('div');
            puzzleDiv.className = 'puzzle-section';
            puzzleDiv.innerHTML = `
                <h3>${puzzleName}</h3>
                <div class="puzzle-text">${puzzleText}</div>
            `;
            chatContainer.appendChild(puzzleDiv);
            
            // 添加交互提示
            const hintDiv = document.createElement('div');
            hintDiv.className = 'hint-section';
            hintDiv.innerHTML = `
                <p>你可以通过提问来获取线索，问题请用"是/不是"能回答的形式。</p>
                <p>当你想猜测汤底时，请以"汤底"开头描述你的推理。</p>
            `;
            chatContainer.appendChild(hintDiv);
            cluesGiven = [];
        } catch (error) {
            chatContainer.innerHTML = `<div class="error">加载谜题失败: ${error.message}</div>`;
        }
    }

    // 处理用户输入
    submitBtn.addEventListener('click', async () => {
        const input = userInput.value.trim();
        if (!input) return;
        
        // 显示用户输入和等待状态
        const waitingSpan = addMessage(input, 'user');
        // 锁定UI
        lockUI();
        
        try {
            let response;
            if (input.startsWith('汤底') || input.startsWith("汤底：")) {
                response = await checkSolution(input.replace(/^汤底[:：]?\s*/, ''));
            } else {
                response = await answerQuestion(input);
            }
            // 替换等待消息为实际回复
            addMessage(response, 'bot', waitingSpan.id);
        } catch (error) {
            // 替换等待消息为错误信息
            addMessage(`处理失败: ${error.message}`, 'error', 'waiting-message');
        } finally {
            // 解锁UI
            unlockUI();
            userInput.value = '';
        }
    });

    // 回答问题
    async function answerQuestion(question) {
        try {
            const messages = [
                { role: "system", content: `你是一个海龟汤游戏主持人，根据以下谜题和规则回答问题：
谜题: ${currentPuzzle}
规则:
1. 先对谜题和问题进行简单分析，然后再给出回答
2. 回答必须用"{是}"、"{不是}"、"{是也不是}"或"{没有关系}"格式
3. 如果问题部分正确回答"{是也不是}"
4. 如果问题与谜题无关回答"{没有关系}"` },
                { role: "user", content: question }
            ];
            
            const response = await callOpenRouterAPI(messages);
            
            // 存储完整response到全局变量方便调试
            window.lastAPIResponse = {
                request: messages,
                response: response
            };
            
            // 从response中提取{}内的回答
            const answerMatch = response.match(/\{(.*?)\}/);
            const answer = answerMatch ? answerMatch[1] : response;
            
            cluesGiven.push({question, answer});
            return answer;
        } catch (error) {
            throw new Error(`回答问题时出错: ${error.message}`);
        }
    }

    // 验证谜底
    async function checkSolution(solution) {
        try {

            const messages = [
                {
                    role: "system", content: `你是一个海龟汤游戏主持人，根据以下谜题验证猜题者的答案：
谜题: ${currentPuzzle}
规则:
1. 先对谜题和猜题者的答案进行简单分析，然后再给出判断结果
2. 判断结果必须用"{完全正确}"、"{部分正确}"或"{完全错误}"格式
3. 可以指出错误或遗漏的部分` },
                { role: "user", content: `汤底: ${solution}` }
            ];

            const response = await callOpenRouterAPI(messages);
            // 存储完整response到全局变量方便调试
            window.lastAPIResponse = {
                request: messages,
                response: response
            };
            
            // 从response中提取{}内的判断
            const resultMatch = response.match(/\{(.*?)\}/);
            const result = resultMatch ? resultMatch[1] : response;
            
            if (result === '完全正确') {
                // 创建完全正确消息
                const correctDiv = document.createElement('div');
                correctDiv.innerHTML = `
                    <span style="font-weight:bold;color:green">完全正确！！！</span>
                    <div>${'谜底：' + currentPuzzle.match(/### 汤底([\s\S]*?)(###|$)/)[1].trim()}</div>
                `;
                chatContainer.appendChild(correctDiv);
                return '';
            }
            return result;
        } catch (error) {
            throw new Error(`验证谜底时出错: ${error.message}`);
        }
    }

    // 调用OpenRouter API
    async function callOpenRouterAPI(messages) {
        const response = await fetch(OPENROUTER_API_URL, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${OPENROUTER_API_KEY}`,
                'HTTP-Referer': window.location.href,
                'X-Title': encodeURIComponent('海龟汤AI助手'),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                model: "deepseek/deepseek-chat-v3-0324:free",
                messages: messages,
                temperature: 0.7
            })
        });

        if (!response.ok) {
            throw new Error(`API请求失败: ${response.status}`);
        }

        const data = await response.json();
        return data.choices[0].message.content;
    }

    // 添加消息到聊天界面
    function addMessage(text, type, replaceId = null) {
        const container = document.createElement('div');
        container.className = 'message-container';
        
        if (type === 'user') {
            // 用户消息
            const userSpan = document.createElement('span');
            userSpan.className = 'user-message';
            userSpan.textContent = text;
            container.appendChild(userSpan);
            
            // 添加等待指示器(使用时间戳确保唯一ID)
            const waitingSpan = document.createElement('span');
            waitingSpan.className = 'waiting-message';
            waitingSpan.id = `waiting-${Date.now()}`;
            waitingSpan.textContent = ' - 等待中...';
            container.appendChild(waitingSpan);
            
            chatContainer.appendChild(container);
            chatContainer.scrollTop = chatContainer.scrollHeight;
            return waitingSpan;
        } else {
            // 处理AI回复
            let responseClass = '';
            const trimmedText = text.trim();
            if (trimmedText === '是') {
                responseClass = 'response-yes';
            } else if (trimmedText === '不是') {
                responseClass = 'response-no';
            } else if (trimmedText === '没有关系') {
                responseClass = 'response-neutral';
            }
            
            if (replaceId) {
                // 替换等待消息
                const waitingElement = document.getElementById(replaceId);
                if (waitingElement) {
                    // 获取父容器
                    const container = waitingElement.parentNode;
                    // 创建新的回复元素
                    const responseSpan = document.createElement('span');
                    responseSpan.className = responseClass;
                    responseSpan.textContent = ` - ${text}`;
                    
                    // 添加隐藏的完整response调试信息(仅通过查看源代码可见)
                    if (window.lastAPIResponse) {
                        const debugDiv = document.createElement('div');
                        debugDiv.style.display = 'none';
                        debugDiv.textContent = `完整响应: ${JSON.stringify(window.lastAPIResponse, null, 2)}`;
                        container.appendChild(debugDiv);
                    }
                    
                    // 替换等待消息
                    container.replaceChild(responseSpan, waitingElement);
                    chatContainer.scrollTop = chatContainer.scrollHeight;
                    return responseSpan;
                }
            }
            
            // 独立AI消息
            const responseSpan = document.createElement('span');
            responseSpan.className = responseClass;
            responseSpan.textContent = text;
            container.appendChild(responseSpan);
            
            // 添加隐藏的完整response调试信息(仅通过查看源代码可见)
            if (window.lastAPIResponse) {
                const debugDiv = document.createElement('div');
                debugDiv.style.display = 'none';
                debugDiv.textContent = `完整响应: ${JSON.stringify(window.lastAPIResponse, null, 2)}`;
                container.appendChild(debugDiv);
            }
            
            chatContainer.appendChild(container);
            chatContainer.scrollTop = chatContainer.scrollHeight;
            return container;
        }
    }

});
