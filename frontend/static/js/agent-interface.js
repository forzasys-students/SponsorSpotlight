class AgentInterface {
    constructor(dashboard) {
        this.dashboard = dashboard;
        this.lastAgentQuery = '';
        this.pendingShare = false;

        this.queryInput = document.getElementById('agent-query-input');
        this.queryButton = document.getElementById('agent-query-button');
        this.responseContainer = document.getElementById('agent-response-container');
        this.loadingSpinner = document.getElementById('agent-loading');
        this.responseElement = document.getElementById('agent-response');
        this.loadingText = this.loadingSpinner?.querySelector('p');
        this.suggestionsContainer = document.getElementById('agent-suggestions');
        this.refreshSuggestionsBtn = document.getElementById('agent-refresh-suggestions');
        this.videoContainer = document.getElementById('agent-video-container');
    }

    init() {
        if (!this.queryButton) return; // Don't initialize if the agent UI isn't present
        this.setupEventListeners();
        this.renderSuggestions();
    }

    setupEventListeners() {
        this.queryButton.addEventListener('click', () => this.handleQuery());

        // Quick action: create clip from rank table
        document.addEventListener('click', (e) => {
            const btn = e.target?.closest('[data-action="suggest-clip"]');
            if (!btn) return;
            const brand = btn.getAttribute('data-brand');
            if (!brand) return;
            this.queryInput.value = `Create a 5-second clip with ${brand}`;
            this.handleQuery();
        });

        // Confirm share button handler
        document.addEventListener('click', (e) => {
            const btn = e.target?.closest('[data-action="confirm-share"]');
            if (!btn) return;
            const localPath = btn.getAttribute('data-local');
            if (!localPath) return;
            this.handleShareConfirmation(localPath);
        });
        
        if (this.refreshSuggestionsBtn) {
            this.refreshSuggestionsBtn.addEventListener('click', () => this.renderSuggestions());
        }
    }

    pollTaskStatus(taskId) {
        const interval = setInterval(() => {
            fetch(`/api/agent_task_status/${taskId}`)
                .then(response => response.json())
                .then(data => {
                    if (data.status !== 'not_found' && this.loadingText) {
                        this.loadingText.textContent = data.message;
                    }

                    if (data.is_complete) {
                        clearInterval(interval);
                        this.loadingSpinner.style.display = 'none';
                        this.responseElement.style.display = 'block';
                        this.renderAgentResponseUI(data.result);
                    }
                })
                .catch(error => {
                    clearInterval(interval);
                    this.loadingSpinner.style.display = 'none';
                    this.responseElement.style.display = 'block';
                    this.responseElement.innerHTML = `<div class="alert alert-danger">Error polling task status: ${error}</div>`;
                });
        }, 2000); // Poll every 2 seconds
    }

    handleQuery() {
        const originalQuery = this.queryInput.value.trim();
        let query = originalQuery;
        if (!query) return;
        this.lastAgentQuery = originalQuery;
        // Human-in-the-loop share: detect explicit share intent, but avoid false positives like "share of voice"
        const isInstagram = /\binstagram\b/i.test(originalQuery);
        const isExplicitShareVerb = /\bshare\s+(it|this|on|to)\b/i.test(originalQuery) || /\b(post|publish)\b/i.test(originalQuery);
        const wantsShare = isInstagram || isExplicitShareVerb;
        if (wantsShare) {
            this.pendingShare = true;
            // Remove trailing explicit share clause only (not phrases like "share of voice")
            query = originalQuery.replace(/\s*(,?\s*and\s+)?(?:share\s+(?:it|this|on|to)[\s\S]*|post[\s\S]*|publish[\s\S]*|instagram[\s\S]*)$/i, '').trim();
            if (!query) query = originalQuery; // fallback safety
        } else {
            this.pendingShare = false;
        }

        this.responseContainer.style.display = 'block';
        this.loadingSpinner.style.display = 'block';
        this.responseElement.style.display = 'none';
        this.loadingText.textContent = "Sending request to agent...";

        fetch(`/api/agent_query/${this.dashboard.fileHash}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: query })
        })
        .then(response => response.json())
        .then(data => {
            if (data.task_id) {
                // This is an async task, start polling
                this.pollTaskStatus(data.task_id);
            } else {
                // This was a sync task (like analysis)
                this.loadingSpinner.style.display = 'none';
                this.responseElement.style.display = 'block';
                this.renderAgentResponseUI(data.response);
            }
        })
        .catch(error => {
            this.loadingSpinner.style.display = 'none';
            this.responseElement.style.display = 'block';
            this.responseElement.innerHTML = `<div class="alert alert-danger">An error occurred: ${error}</div>`;
        });
    }
    
    handleShareConfirmation(localPath) {
        // Trigger async share flow via agent
        this.responseContainer.style.display = 'block';
        this.loadingSpinner.style.display = 'block';
        this.responseElement.style.display = 'none';
        this.loadingText.textContent = 'Submitting to Instagram...';
        fetch(`/api/agent_query/${this.dashboard.fileHash}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: `Share the clip at ${localPath} on Instagram. Yes, I confirm.` })
        })
        .then(r => r.json())
        .then(data => {
            if (data.task_id) {
                this.pollTaskStatus(data.task_id);
            } else {
                this.loadingSpinner.style.display = 'none';
                this.responseElement.style.display = 'block';
                this.responseElement.innerHTML = this.simpleMarkdownToHtml(data.response || '');
            }
        })
        .catch(err => {
            this.loadingSpinner.style.display = 'none';
            this.responseElement.style.display = 'block';
            this.responseElement.innerHTML = `<div class="alert alert-danger">Failed to submit share: ${err}</div>`;
        });
        this.pendingShare = false;
    }

    pickBrand(idx, fallback) {
        const keys = Object.keys(this.dashboard.logoStats);
        return keys[idx] || fallback;
    };

    suggestionGroups() {
        return ([
            {
                title: 'Analysis',
                items: [
                    { icon: 'bi-robot', hint: 'AI analysis', text: 'Analyze the video and summarize key insights' },
                    { icon: 'bi-trophy', hint: 'Top performers', text: 'Which are the top 3 brands by exposure percentage?' },
                    { icon: 'bi-bar-chart', hint: 'Compare', text: `Compare ${this.pickBrand(0,'Brand A')} vs ${this.pickBrand(1,'Brand B')} exposure` },
                    { icon: 'bi-filter', hint: 'Low exposure', text: 'List brands with less than 1% exposure' },
                ]
            },
            {
                title: 'Video editor',
                items: [
                    { icon: 'bi-film', hint: 'Clip (10s)', text: `Find the best 10-second clip featuring ${this.pickBrand(0,'top brand')}` },
                    this.dashboard.fileType === 'video' ? { icon: 'bi-scissors', hint: 'Clip (5s)', text: `Create a 5-second clip with ${this.pickBrand(0,'top brand')}` } : null,
                    this.dashboard.fileType === 'video' ? { icon: 'bi-scissors', hint: 'Clip (4s)', text: `Create a 4-second clip with ${this.pickBrand(1,'another brand')}` } : null,
                    this.dashboard.fileType === 'video' ? { icon: 'bi-lightning-charge', hint: 'Most exposure + share', text: `Find the most exposure time of ${this.pickBrand(0,'top brand')}, create a clip with duration of 5 seconds and share it on Instagram` } : null,
                ].filter(Boolean)
            },
            this.dashboard.fileType === 'video' ? {
                title: 'Highlights',
                items: [
                    { icon: 'bi-lightning-charge', hint: 'Most exposure', text: `Find the most exposure time of ${this.pickBrand(0,'top brand')}, create a clip with duration of 3 seconds` },
                ]
            } : null,
            this.dashboard.fileType === 'video' ? {
                title: 'Social',
                items: [
                    { icon: 'bi-hash', hint: 'Social caption', text: `Generate a caption to share a clip of ${this.pickBrand(2,'third brand')}` },
                ]
            } : null,
        ].filter(Boolean));
    }

    renderSuggestions() {
        if (!this.suggestionsContainer) return;
        const groups = this.suggestionGroups();
        this.suggestionsContainer.innerHTML = groups.map(g => `
            <div class="suggestion-group">
                <div class="suggestion-group-title">${g.title}</div>
                ${g.items.map(({ icon, hint, text }) => `
                    <div class="suggestion-item d-flex align-items-start">
                        <div class="suggestion-icon me-2"><i class="bi ${icon}"></i></div>
                        <div class="flex-grow-1">
                            <div class="suggestion-title">${text}</div>
                            <div class="suggestion-hint">${hint}</div>
                        </div>
                    </div>
                `).join('')}
            </div>
        `).join('');
        Array.from(this.suggestionsContainer.querySelectorAll('.suggestion-item')).forEach(item => {
            item.addEventListener('click', () => {
                const title = item.querySelector('.suggestion-title')?.textContent || '';
                this.queryInput.value = title;
                this.queryInput.focus();
            });
        });
    }

    renderAgentResponseUI(markdown) {
        const rawUrl = this.extractMp4Url(markdown);
        const explicitPath = this.parseClipPath(markdown);
        const url = this.normalizeStaticUrl(explicitPath || rawUrl);

        let cleanedMarkdown = markdown;
        if (rawUrl) {
            const lines = markdown.split(/\n+/);
            cleanedMarkdown = lines.filter(l => !l.includes('.mp4')).join('\n');
        }
        // Detect embedded RANK_JSON for structured rendering (tolerant to single quotes)
        const rankJson = this.parseRankJson(cleanedMarkdown);
        // Remove the RANK_JSON line from prose before rendering markdown
        const proseWithoutRank = cleanedMarkdown
            .split(/\n+/)
            .filter(line => !/^\s*RANK_JSON:\s*/.test(line))
            .join('\n');
        const contentHtml = this.simpleMarkdownToHtml(proseWithoutRank || '');

        if (url) {
            const rankTableHtml = rankJson ? this.renderRankTable(rankJson) : '';
            // If the last query asked to share, show a confirmation CTA instead of auto-sharing
            const wantShare = this.pendingShare || (this.lastAgentQuery || '').toLowerCase().includes('share');
            const rawLocal = explicitPath || rawUrl;
            const confirmShareHtml = wantShare && rawLocal ? `
                <div class="alert alert-warning d-flex justify-content-between align-items-center mt-2">
                    <div>
                        <i class="bi bi-question-circle me-2"></i>
                        Ready to post this clip to Instagram?
                    </div>
                    <button class="btn btn-sm btn-primary" data-action="confirm-share" data-local="${rawLocal}">Share to Instagram</button>
                </div>
            ` : '';
            this.responseElement.innerHTML = `
                <div class="agent-result-card card">
                    <div class="card-header d-flex align-items-center justify-content-between">
                        <div class="d-flex align-items-center">
                            <i class="bi bi-check-circle-fill text-success me-2"></i>
                            <strong>Clip created</strong>
                        </div>
                        <div class="d-flex gap-2">
                            <a class="btn btn-sm btn-outline-primary" href="${url}" target="_blank" rel="noopener">Open clip</a>
                        </div>
                    </div>
                    <div class="card-body">
                        <div class="text-muted small mb-2">${contentHtml}</div>
                        ${rankTableHtml}
                        <code class="small text-secondary">${url}</code>
                        ${confirmShareHtml}
                    </div>
                </div>
            `;
            this.renderInlineVideoIfAny(url, true);
        } else {
            const rankTableHtml = rankJson ? this.renderRankTable(rankJson) : '';
            this.responseElement.innerHTML = `
                <div class="agent-result-card card">
                    <div class="card-header d-flex align-items-center">
                        <i class="bi bi-robot me-2"></i>
                        <strong>Agent response</strong>
                    </div>
                    <div class="card-body">
                        ${contentHtml}
                        ${rankTableHtml}
                    </div>
                </div>
            `;
            if (this.videoContainer) {
                this.videoContainer.style.display = 'none';
                this.videoContainer.innerHTML = '';
            }
        }
    }

    parseRankJson(markdown) {
        if (!markdown) return null;
        const match = markdown.match(/RANK_JSON:\s*({[\s\S]*?})\s*$/m);
        if (!match) return null;
        const blob = match[1];
        // Try strict JSON first
        try { return JSON.parse(blob); } catch (_) {}
        // Normalize single quotes and trailing commas then retry
        try {
            let normalized = blob.replace(/'/g, '"');
            normalized = normalized.replace(/,(\s*[}\]])/g, '$1');
            return JSON.parse(normalized);
        } catch (_) {
            return null;
        }
    }

    parseClipPath(markdown) {
        if (!markdown) return null;
        const match = markdown.match(/^\s*CLIP_PATH:\s*(.+)$/m);
        if (!match) return null;
        let p = match[1].trim();
        if (p.startsWith('sandbox:')) p = p.slice('sandbox:'.length);
        return p.replace(/^`|`$/g, '').replace(/^"|"$/g, '').replace(/^'|'$/g, '');
    }

    renderRankTable(rankJson) {
        const items = Array.isArray(rankJson.items) ? rankJson.items : [];
        if (!items.length) return '';
        const metric = rankJson.metric || '';
        const dir = rankJson.direction || 'desc';
        const header = `Top ${items.length} by ${metric} (${dir})`;
        return `
            <div class="table-responsive mt-2">
                <table class="table table-sm align-middle mb-2 agent-table">
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Brand</th>
                            <th>${metric}</th>
                            <th class="text-end">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${items.map((it, idx) => `
                            <tr>
                                <td>${idx + 1}</td>
                                <td>${it.brand}</td>
                                <td>${it.formatted_value ?? it.value}</td>
                                <td class="text-end">
                                    ${this.dashboard.fileType === 'video' ? `<button type="button" class="btn btn-sm btn-outline-secondary" data-action="suggest-clip" data-brand="${it.brand}">Create 5s clip</button>` : ''}
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    }

    extractMp4Url(markdown) {
        if (!markdown) return null;
        // Common markdown and HTML link patterns
        let m = markdown.match(/\(([^)]+\.mp4)\)/i) || markdown.match(/href=["']([^"']+\.mp4)["']/i);
        if (m && m[1]) return m[1];
        // Backticked code path `...mp4`
        m = markdown.match(/`([^`]+\.mp4)`/i);
        if (m && m[1]) return m[1];
        // Direct static served path anywhere in the text
        m = markdown.match(/(\/static\/results\/[\S]+?\.mp4)/i);
        if (m && m[1]) return m[1];
        // Fallback: any token ending with .mp4
        m = markdown.match(/([\S]+?\.mp4)/i);
        return m ? m[1] : null;
    }

    normalizeStaticUrl(rawUrl) {
        if (!rawUrl) return null;
        const marker = '/static/results/';
        const pos = rawUrl.indexOf(marker);
        if (pos === -1) return null;
        let url = rawUrl.slice(pos);
        if (!url.startsWith('/')) url = '/' + url;
        return url;
    }

    renderInlineVideoIfAny(sourceOrMarkdown, isUrl = false) {
        try {
            if (!this.videoContainer || !sourceOrMarkdown) return;
            let url = null;
            if (isUrl) {
                url = sourceOrMarkdown;
            } else {
                const raw = this.extractMp4Url(sourceOrMarkdown);
                url = this.normalizeStaticUrl(raw);
            }
            if (!url) return;

            // Build a video player
            const videoHtml = `
                <div class="card">
                    <div class="card-header d-flex align-items-center">
                        <i class="bi bi-play-circle me-2"></i>
                        <strong>Generated clip preview</strong>
                    </div>
                    <div class="card-body">
                        <video controls preload="metadata" style="width: 100%; max-height: 420px; border-radius: 4px;">
                            <source src="${url}" type="video/mp4">
                            Your browser does not support the video tag.
                        </video>
                    </div>
                </div>
            `;
            this.videoContainer.innerHTML = videoHtml;
            this.videoContainer.style.display = 'block';
            // Ensure suggestions column visually aligns with new height while preserving scroll when shorter
            const leftCol = document.getElementById('agent-left-col');
            const suggHeader = document.getElementById('agent-suggestions-header');
            const suggList = document.getElementById('agent-suggestions');
            if (leftCol && suggList) {
                const leftHeight = leftCol.getBoundingClientRect().height;
                const headerHeight = (suggHeader?.getBoundingClientRect().height || 0);
                // Add a small padding offset
                const target = Math.max(280, leftHeight - headerHeight - 24);
                suggList.style.maxHeight = `${target}px`;
                suggList.style.overflowY = 'auto';
            }
        } catch (_) {
            // no-op
        }
    }

    simpleMarkdownToHtml(markdown) {
        // Basic markdown conversion for demonstration purposes.
        // 1) Convert Markdown links first: [text](url)
        const mdLink = /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g;
        let html = (markdown || '').replace(mdLink, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
        // 2) Autolink bare URLs, avoiding those inside attributes or tags by requiring start or whitespace before
        const autoLink = /(^|\s)(https?:\/\/[^\s<]+)/g;
        html = html.replace(autoLink, (m, p1, p2) => `${p1}<a href="${p2}" target="_blank" rel="noopener noreferrer">${p2}</a>`);
        // 3) Headings, quotes, emphasis, lists
        return html
            .replace(/^### (.*$)/gim, '<h3>$1</h3>')
            .replace(/^## (.*$)/gim, '<h2>$1</h2>')
            .replace(/^# (.*$)/gim, '<h1>$1</h1>')
            .replace(/^\> (.*$)/gim, '<blockquote>$1</blockquote>')
            .replace(/\*\*(.*)\*\*/gim, '<strong>$1</strong>')
            .replace(/\*(.*)\*/gim, '<em>$1</em>')
            .replace(/^- (.*$)/gim, '<li>$1</li>')
            .replace(/^\* (.*$)/gim, '<li>$1</li>')
            .replace(/(\n\s*-\s*.*)+/gim, (match) => `<ul>${match.replace(/^\s*-\s*/gm, '<li>')}</ul>`)
            .replace(/(\n\s*\*\s*.*)+/gim, (match) => `<ul>${match.replace(/^\s*\*\s*/gm, '<li>')}</ul>`)
            .replace(/\n$/gim, '<br />');
    }
}
