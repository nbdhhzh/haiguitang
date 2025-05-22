// 初始化IndexedDB
let db;
const initDB = new Promise((resolve) => {
    const request = indexedDB.open('HaiGuiTangDB', 1);
    
    request.onupgradeneeded = (event) => {
        db = event.target.result;
        if (!db.objectStoreNames.contains('userRecords')) {
            db.createObjectStore('userRecords', { keyPath: ['puzzle', 'ip'] });
        }
    };
    
    request.onsuccess = (event) => {
        db = event.target.result;
        resolve();
    };
    
    request.onerror = (event) => {
        console.error('数据库打开失败:', event.target.error);
    };
});

// 保存用户记录
async function saveUserRecord(puzzleFile, recordData) {
    try {
        const {ip} = await fetch('https://api.ipify.org?format=json').then(res => res.json());
        const puzzleName = puzzleFile.replace('.md', '');
        
        const response = await fetch('/save-record', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                puzzle: puzzleName,
                ip: ip,
                data: recordData
            })
        });
        
        if (!response.ok) {
            throw new Error('保存记录失败');
        }
        return true;
    } catch (error) {
        console.error('保存记录出错:', error);
        return false;
    }
}

// 加载用户记录
async function loadUserRecord(puzzleFile) {
    try {
        const {ip} = await fetch('https://api.ipify.org?format=json').then(res => res.json());
        const puzzleName = puzzleFile.replace('.md', '');
        const response = await fetch(`/load-record?puzzle=${encodeURIComponent(puzzleName)}&ip=${encodeURIComponent(ip)}`);
        if (!response.ok) {
            console.log('没有找到记录文件');
            return null;
        }
        const data = await response.json();
        console.log('加载的记录数据:', data);
        return data;
    } catch (error) {
        console.error('加载记录出错:', error);
        return null;
    }
}

// 海龟汤游戏主逻辑 - 对话模式
document.addEventListener('DOMContentLoaded', function() {
    const chatContainer = document.getElementById('puzzle-display');
    const userInput = document.getElementById('user-guess');
    const submitBtn = document.getElementById('submit-guess');
    const getHintBtn = document.getElementById('get-hint');
    const solveBtn = document.getElementById('solve');
    let currentPuzzle = null;
    let currentPuzzleFile = null;
    let cluesGiven = [];

    // 保存状态
    function saveState() {
        const state = {
            puzzle: currentPuzzle,
            file: currentPuzzleFile,
            clues: cluesGiven,
            chatHistory: document.getElementById('puzzle-display').innerHTML
        };
        
        // 直接保存到localStorage
        localStorage.setItem('hgtState', JSON.stringify(state));
        
        // 同时保存到特定谜题记录
        if (currentPuzzleFile) {
            saveUserRecord(currentPuzzleFile, state);
        }
    }

    // 恢复状态
    async function restoreState(puzzleFile) {
        // 先尝试从特定谜题记录恢复
        if (puzzleFile) {
            try {
                const record = await loadUserRecord(puzzleFile);
                console.log('从服务器加载的记录:', record);  // 调试日志
                if (record) {
                    currentPuzzle = record.puzzle;
                    currentPuzzleFile = record.file;
                    cluesGiven = record.clues || [];
                    document.getElementById('puzzle-display').innerHTML = record.chatHistory || '';
                    return true;
                }
            } catch (error) {
                console.error('从服务器恢复状态失败:', error);
            }
        }
        loadPuzzle(puzzleFile);
    }

    // 获取提示按钮
    getHintBtn.addEventListener('click', async () => {
        if (!currentPuzzle) return;
        
        const waitingSpan = addMessage('获取提示中...', 'bot');
        lockUI();
        
        try {
            const response = await callOpenRouterAPI([
                { role: "system", content: `你是一个海龟汤游戏主持人，根据以下谜题提供一个不泄露谜底的提示：
谜题: 
${currentPuzzle}

规则:
1. 提示应该引导思考但不要直接给出答案
2. 提示应该简短明了，以 "提示：" 开头` },
                { role: "user", content: "请给我一个提示" }
            ]);
            
            const container = document.createElement('div');
            container.className = 'message-container';
            
            const responseSpan = document.createElement('span');
            responseSpan.className = 'bot-message';
            responseSpan.textContent = response;
            container.appendChild(responseSpan);
            
            waitingSpan.parentNode.replaceChild(container, waitingSpan);
            saveState();
        } catch (error) {
            addMessage(`获取提示失败: ${error.message}`, 'error', waitingSpan.id);
        } finally {
            unlockUI();
        }
    });
    
    // 解答按钮
    solveBtn.addEventListener('click', () => {
        if (!currentPuzzle) return;
        
        const solutionMatch = currentPuzzle.match(/### 汤底([\s\S]*?)(###|$)/);
        if (solutionMatch) {
            addMessage('汤底：' + solutionMatch[1].trim(), 'bot');
            saveState();
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
    
    // 从URL参数获取puzzle文件名
    const urlParams = new URLSearchParams(window.location.search);
    const puzzleFile = urlParams.get('puzzle');
    
    // 处理URL参数中的谜题
    if (puzzleFile) {
        localStorage.removeItem('htgState');
        restoreState(puzzleFile)
    } 
    // 没有URL参数则加载随机谜题
    else {
        loadRandomPuzzle();
    }
    
    async function loadPuzzle(fileName) {
        try {
            // 完全重置状态
            localStorage.removeItem('hgtState');
            currentPuzzle = null;
            currentPuzzleFile = null;
            cluesGiven = [];
            chatContainer.innerHTML = '';
            
            const response = await fetch(`/puzzles/${fileName}`);
            currentPuzzle = await response.text();
            currentPuzzleFile = fileName;
            
            // 更健壮的谜题内容解析
            const puzzleParts = currentPuzzle.split('### 汤面');
            if (puzzleParts.length < 2) {
                throw new Error('无效的谜题格式: 缺少汤面部分');
            }
            
            const solutionParts = puzzleParts[1].split('### 汤底');
            if (solutionParts.length < 2) {
                throw new Error('无效的谜题格式: 缺少汤底部分');
            }
            
            const puzzleText = solutionParts[0].trim();
            const puzzleName = fileName.replace('.md', '');
            
            chatContainer.innerHTML = '';
            
            const puzzleDiv = document.createElement('div');
            puzzleDiv.className = 'puzzle-section';
            puzzleDiv.innerHTML = `
                <h3>${puzzleName}</h3>
                <div class="puzzle-text">${puzzleText}</div>
            `;
            chatContainer.appendChild(puzzleDiv);
            
            const hintDiv = document.createElement('div');
            hintDiv.className = 'hint-section';
            hintDiv.innerHTML = `
                你可以通过提问来获取线索，问题请用"是/不是"能回答的形式。<br>
                当你想猜测汤底时，请以"汤底"开头描述你的推理。
            `;
            chatContainer.appendChild(hintDiv);
            cluesGiven = [];
            saveState();
        } catch (error) {
            chatContainer.innerHTML = `<div class="error">加载谜题失败: ${error.message}</div>`;
        }
    }
    
    async function loadRandomPuzzle() {
        try {
            const response = await fetch('/puzzles/');
            const text = await response.text();
            
            const parser = new DOMParser();
            const htmlDoc = parser.parseFromString(text, 'text/html');
            const links = htmlDoc.querySelectorAll('a[href$=".md"]');
            
            if (links.length === 0) {
                throw new Error('没有找到任何谜题文件');
            }
            
            const randomIndex = Math.floor(Math.random() * links.length);
            const randomFile = links[randomIndex].getAttribute('href');
            
            await loadPuzzle(randomFile);
        } catch (error) {
            chatContainer.innerHTML = `<div class="error">加载随机谜题失败: ${error.message}</div>`;
        }
    }

    // 处理用户输入
    submitBtn.addEventListener('click', async function handleSubmit() {
        if (!currentPuzzle) {
            addMessage('请先加载一个谜题', 'error');
            return;
        }
        
        const input = userInput.value.trim();
        if (!input) return;
        
        const waitingSpan = addMessage(input, 'user');
        lockUI();
        
        try {
            let response;
            if (input.startsWith('汤底') || input.startsWith("汤底：")) {
                response = await checkSolution(input.replace(/^汤底[:：]?\s*/, ''));
            } else {
                response = await answerQuestion(input);
            }
            addMessage(response, 'bot', waitingSpan.id);
            saveState();
        } catch (error) {
            addMessage(`处理失败: ${error.message}`, 'error', 'waiting-message');
        } finally {
            unlockUI();
            userInput.value = '';
        }
    });

    // 回答问题
    async function answerQuestion(question) {
        try {
            const messages = [
                {
                    role: "system", content: `你是一个海龟汤游戏主持人，根据以下谜题和规则，对猜题者的问题进行判断：
谜题: 
${currentPuzzle}

规则:
1. 先在<think></think>中对谜题和猜题者的问题进行简单分析，然后再给出判断
2. 最后的判断用大括号括起来，必须是"{是}"、"{不是}"、"{是也不是}"或"{没有关系}"四者其一
3. 如果问题部分正确回答"{是也不是}"
4. 如果问题与谜题无关回答"{没有关系}"` },
                { role: "user", content: question }
            ];
            
            const response = await callOpenRouterAPI(messages);
            
            window.lastAPIResponse = {
                request: messages,
                response: response
            };
            
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
                    role: "system", content: `你是一个海龟汤游戏主持人，根据以下谜题判断猜题者的答案是否完整、正确：
谜题: 
${currentPuzzle}

规则:
1. 先在<think></think>中对谜题和猜题者的答案进行简单分析，然后再给出判断
2. 最后的判断用大括号括起来，必须是"{完全正确}"、"{部分正确}"或"{完全错误}"三者其一
3. 如果答案部分正确却很不完整，回答"{部分正确}"` },
                { role: "user", content: `汤底: ${solution}` }
            ];

            const response = await callOpenRouterAPI(messages);
            window.lastAPIResponse = {
                request: messages,
                response: response
            };
            
            const resultMatch = response.match(/\{(.*?)\}/);
            const result = resultMatch ? resultMatch[1] : response;
            
            if (result === '完全正确') {
                const solution = currentPuzzle.match(/### 汤底([\s\S]*?)(###|$)/)[1].trim();
                const correctDiv = document.createElement('div');
                correctDiv.innerHTML = `
                    <span style="font-weight:bold;color:green">完全正确！！！</span>
                    <div>${'汤底：' + solution}</div>
                `;
                chatContainer.appendChild(correctDiv);
                
                // 添加弹窗逻辑
                const modal = document.createElement('div');
                modal.style.position = 'fixed';
                modal.style.top = '50%';
                modal.style.left = '50%';
                modal.style.transform = 'translate(-50%, -50%)';
                modal.style.backgroundColor = '#fff';
                modal.style.padding = '30px';
                modal.style.borderRadius = '12px';
                modal.style.boxShadow = '0 0 25px rgba(0,0,0,0.4)';
                modal.style.zIndex = '1000';
                modal.style.maxWidth = '600px';
                modal.style.width = '90%';
                modal.style.maxHeight = '90vh';
                modal.style.overflow = 'auto';
                modal.style.fontFamily = 'Arial, sans-serif';
                modal.innerHTML = `
                    <h2 style="color: #4CAF50; margin-top: 0; text-align: center;">完全正确！！！</h2>
                    <p style="text-align: center;">恭喜你解开了这个谜题！</p>
                    <div style="margin: 20px 0;">
                        <h3 style="margin-bottom: 10px;">汤底：</h3>
                        <p style="background: #f5f5f5; padding: 15px; border-radius: 8px;">${solution}</p>
                    </div>
                    <div style="margin: 25px 0;">
                        <div style="margin-bottom: 15px;">
                            <label style="display: block; margin-bottom: 8px; font-weight: bold;">趣味性评分:</label>
                            <div class="star-rating">
                                ${[1,2,3,4,5].map(i => `<span class="star" data-rating="fun" data-value="${i}">★</span>`).join('')}
                            </div>
                        </div>
                        <div>
                            <label style="display: block; margin-bottom: 8px; font-weight: bold;">逻辑性评分:</label>
                            <div class="star-rating">
                                ${[1,2,3,4,5].map(i => `<span class="star" data-rating="logic" data-value="${i}">★</span>`).join('')}
                            </div>
                        </div>
                    </div>
                    <button id="submitRating" style="display: block; width: 100%; padding: 12px; background: #4CAF50; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; margin-top: 15px;">提交评分</button>
                `;
                document.body.appendChild(modal);
                
                // 添加星级评分交互
                modal.querySelectorAll('.star').forEach(star => {
                    star.style.cursor = 'pointer';
                    star.style.fontSize = '24px';
                    star.style.color = '#ccc';
                    star.style.marginRight = '5px';
                    
                    star.addEventListener('mouseover', function() {
                        const ratingType = this.getAttribute('data-rating');
                        const value = parseInt(this.getAttribute('data-value'));
                        highlightStars(ratingType, value);
                    });
                    
                    star.addEventListener('click', function() {
                        const ratingType = this.getAttribute('data-rating');
                        const value = parseInt(this.getAttribute('data-value'));
                        modal.dataset[`${ratingType}Rating`] = value;
                    });
                });
                
                // 添加提交按钮事件 (改为async函数)
                document.getElementById('submitRating').addEventListener('click', async () => {
                    const funRating = modal.dataset.funRating || 0;
                    const logicRating = modal.dataset.logicRating || 0;
                    
                    if (funRating > 0 && logicRating > 0) {
                        // 保存评分到本地存储和服务器
                        const ratingData = {
                            puzzle: currentPuzzle,
                            funRating: funRating,
                            logicRating: logicRating,
                            date: new Date().toISOString()
                        };
                        
                        // 本地存储
                        const ratings = JSON.parse(localStorage.getItem('puzzleRatings') || '[]');
                        ratings.push(ratingData);
                        localStorage.setItem('puzzleRatings', JSON.stringify(ratings));
                        
                        // 服务器存储
                        // if (currentPuzzleFile) {
                        //     try {
                        //         await saveUserRecord(currentPuzzleFile, ratingData);
                        //     } catch (error) {
                        //         console.error('保存评分记录失败:', error);
                        //     }
                        // }
                        
                        // 在主页面显示评分结果
                        const ratingResult = document.createElement('div');
                        ratingResult.className = 'rating-result';
                        ratingResult.innerHTML = `
                            <p>趣味性评分: ${'★'.repeat(funRating)}</p>
                            <p>逻辑性评分: ${'★'.repeat(logicRating)}</p>
                        `;
                        chatContainer.appendChild(ratingResult);
                        
                        // 直接关闭弹窗
                        document.body.removeChild(modal);
                        saveState();
                    } else {
                        alert('请完成两项评分后再提交');
                    }
                });
                
                function highlightStars(ratingType, value) {
                    modal.querySelectorAll(`.star[data-rating="${ratingType}"]`).forEach(star => {
                        const starValue = parseInt(star.getAttribute('data-value'));
                        star.style.color = starValue <= value ? '#FFD700' : '#ccc';
                    });
                }
                
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
                model: `${DEFAULT_MODEL}`,
                messages: messages,
                temperature: 0.7
            })
        });

        if (!response.ok) {
            throw new Error(`API请求失败: ${response.status}`);
        }

        const data = await response.json();
        console.log(messages)
        console.log(data);
        return data.choices[0].message.content;
    }

    // 添加消息到聊天界面
    function addMessage(text, type, replaceId = null) {
        const container = document.createElement('div');
        container.className = 'message-container';
        
        if (type === 'user') {
            const userSpan = document.createElement('span');
            userSpan.className = 'user-message';
            userSpan.textContent = text;
            container.appendChild(userSpan);
            
            const waitingSpan = document.createElement('span');
            waitingSpan.className = 'waiting-message';
            waitingSpan.id = `waiting-${Date.now()}`;
            waitingSpan.textContent = ' - 等待中...';
            container.appendChild(waitingSpan);
            
            chatContainer.appendChild(container);
            chatContainer.scrollTop = chatContainer.scrollHeight;
            return waitingSpan;
        } else {
            let responseClass = '';
            const trimmedText = text.trim();
            if (trimmedText === '是') {
                responseClass = 'response-yes';
            } else if (trimmedText === '不是') {
                responseClass = 'response-no';
            } else {
                responseClass = 'response-neutral';
            }
            
            if (replaceId) {
                const waitingElement = document.getElementById(replaceId);
                if (waitingElement) {
                    const container = waitingElement.parentNode;
                    const responseSpan = document.createElement('span');
                    responseSpan.className = responseClass;
                    responseSpan.textContent = ` - ${text}`;
                    
                    if (window.lastAPIResponse) {
                        const debugDiv = document.createElement('div');
                        debugDiv.style.display = 'none';
                        debugDiv.textContent = `完整响应: ${JSON.stringify(window.lastAPIResponse, null, 2)}`;
                        container.appendChild(debugDiv);
                    }
                    
                    container.replaceChild(responseSpan, waitingElement);
                    chatContainer.scrollTop = chatContainer.scrollHeight;
                    return responseSpan;
                }
            }
            
            const responseSpan = document.createElement('span');
            responseSpan.className = responseClass;
            responseSpan.textContent = text;
            container.appendChild(responseSpan);
            
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
