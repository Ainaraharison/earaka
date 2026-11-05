/* Learning Streak Builder – Frontend JS */
(function () {
    "use strict";

    // ─── Helpers ─────────────────────────────────────────────────────────────
    const $ = (s) => document.querySelector(s);
    const $$ = (s) => document.querySelectorAll(s);

    async function api(path, opts = {}) {
        const res = await fetch(`/api${path}`, {
            ...opts,
            headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
        });
        const text = await res.text();
        let data;
        try {
            data = JSON.parse(text);
        } catch {
            throw new Error("Le serveur a renvoyé une réponse inattendue. Vérifie que l'app est lancée.");
        }
        if (!res.ok) throw new Error(data.error || "Erreur serveur");
        return data;
    }

    function toast(msg, type = "info") {
        const el = document.createElement("div");
        el.className = `toast ${type}`;
        el.textContent = msg;
        $("#toast-container").appendChild(el);
        setTimeout(() => el.remove(), 4000);
    }

    function show(el) { if (el) el.classList.remove("hidden"); }
    function hide(el) { if (el) el.classList.add("hidden"); }
    function esc(str) {
        const d = document.createElement("div");
        d.textContent = str;
        return d.innerHTML;
    }
    function mdToHtml(text) {
        return esc(text).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    }
    function getInitials(name) {
        if (!name) return "?";
        return name.slice(0, 2).toUpperCase();
    }

    // ─── Theme ───────────────────────────────────────────────────────────────
    function applyTheme(theme) {
        document.documentElement.setAttribute("data-theme", theme);
        localStorage.setItem("earaka-theme", theme);
        const btn = $("#btn-theme-toggle");
        if (!btn) return;
        const icon = btn.querySelector(".theme-icon");
        const label = btn.querySelector(".theme-label");
        if (theme === "dark") {
            if (icon) icon.textContent = "☀️";
            if (label) label.textContent = "Mode clair";
        } else {
            if (icon) icon.textContent = "🌙";
            if (label) label.textContent = "Mode sombre";
        }
    }

    applyTheme(localStorage.getItem("earaka-theme") || "light");

    document.addEventListener("click", (e) => {
        if (e.target.closest("#btn-theme-toggle")) {
            const current = document.documentElement.getAttribute("data-theme");
            applyTheme(current === "dark" ? "light" : "dark");
        }
    });

    // ─── Auth ────────────────────────────────────────────────────────────────
    const landingScreen = $("#landing-screen");
    const authScreen = $("#auth-screen");
    const appScreen = $("#app-screen");

    let currentUser = "";
    let currentInterests = [];
    let lbPeriod = "all";

    function openAuth(tab) {
        $$(".auth-tab").forEach((t) => t.classList.remove("active"));
        $$(".auth-panel").forEach((p) => p.classList.remove("active"));
        const target = $(`.auth-tab[data-tab="${tab}"]`);
        if (target) {
            target.classList.add("active");
            $(`#panel-${tab}`).classList.add("active");
        }
        authScreen.classList.add("active");
    }

    function closeAuth() { authScreen.classList.remove("active"); }

    const _nav = { login: $("#btn-nav-login"), register: $("#btn-nav-register") };
    const _hero = { start: $("#btn-hero-start"), login: $("#btn-hero-login") };
    const _cta = { start: $("#btn-cta-start") };

    if (_nav.login)      _nav.login.addEventListener("click", () => openAuth("login"));
    if (_nav.register)   _nav.register.addEventListener("click", () => openAuth("register"));
    if (_hero.start)     _hero.start.addEventListener("click", () => openAuth("register"));
    if (_hero.login)     _hero.login.addEventListener("click", () => openAuth("login"));
    if (_cta.start)      _cta.start.addEventListener("click", () => openAuth("register"));

    const _modalOverlay = $("#modal-overlay");
    const _authClose = $("#btn-auth-close");
    if (_modalOverlay) _modalOverlay.addEventListener("click", closeAuth);
    if (_authClose)    _authClose.addEventListener("click", closeAuth);

    $$(".auth-tab").forEach((tab) => {
        tab.addEventListener("click", () => {
            $$(".auth-tab").forEach((t) => t.classList.remove("active"));
            $$(".auth-panel").forEach((p) => p.classList.remove("active"));
            tab.classList.add("active");
            $(`#panel-${tab.dataset.tab}`).classList.add("active");
        });
    });

    async function checkSession() {
        try {
            const d = await api("/me");
            if (d.logged_in) enterApp(d.username, d.interests);
        } catch { /* not logged in */ }
    }

    function updateGreeting(username) {
        const el = $("#dash-greeting");
        if (!el) return;
        const hour = new Date().getHours();
        const greet = hour < 12 ? "Bonjour" : hour < 18 ? "Bon après-midi" : "Bonsoir";
        el.textContent = `${greet}, ${username} 👋`;
    }

    function enterApp(username, interests) {
        currentUser = username;
        currentInterests = interests || [];
        landingScreen.classList.remove("active");
        authScreen.classList.remove("active");
        appScreen.classList.add("active");
        $("#nav-user").textContent = username;
        const avatarEl = $("#sidebar-avatar-init");
        if (avatarEl) avatarEl.textContent = getInitials(username);
        updateGreeting(username);
        if (currentInterests.length) {
            renderTags(currentInterests);
            renderSubjectPills(currentInterests);
        }
        loadDashboard();
        if (!localStorage.getItem("earaka-tour-done")) setTimeout(startTour, 700);
    }

    function exitApp() {
        currentUser = "";
        currentInterests = [];
        appScreen.classList.remove("active");
        authScreen.classList.remove("active");
        landingScreen.classList.add("active");
        $("#login-email").value = "";
        $("#login-password").value = "";
        $("#login-error").textContent = "";
    }

    $("#btn-login").addEventListener("click", async () => {
        const email = $("#login-email").value.trim();
        const password = $("#login-password").value;
        if (!email || !password) return;
        try {
            await api("/login", { method: "POST", body: JSON.stringify({ email, password }) });
            const me = await api("/me");
            enterApp(me.username, me.interests);
        } catch (e) {
            $("#login-error").textContent = e.message;
        }
    });

    $("#login-password").addEventListener("keydown", (e) => {
        if (e.key === "Enter") $("#btn-login").click();
    });

    $("#btn-register").addEventListener("click", async () => {
        const username = $("#register-username").value.trim();
        const email = $("#register-email").value.trim();
        const password = $("#register-password").value;
        const confirm = $("#register-confirm").value;
        if (!username || !email || !password) return;
        if (password !== confirm) {
            $("#register-error").textContent = "Les mots de passe ne correspondent pas";
            return;
        }
        try {
            await api("/register", { method: "POST", body: JSON.stringify({ username, email, password }) });
            const me = await api("/me");
            enterApp(me.username, me.interests);
            toast("Bienvenue ! 🎉", "success");
        } catch (e) {
            $("#register-error").textContent = e.message;
        }
    });

    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get("error") === "oauth_failed") {
        openAuth("login");
        $("#login-error").textContent = "Connexion Google échouée, réessaie.";
        history.replaceState(null, "", "/");
    }

    $("#btn-logout").addEventListener("click", async () => {
        await api("/logout", { method: "POST" });
        exitApp();
    });

    // ─── Mobile burger nav ────────────────────────────────────────────────────
    const mobileNavOverlay = $("#mobile-nav-overlay");
    const sidebarEl = $(".sidebar");

    function closeMobileNav() {
        if (sidebarEl) sidebarEl.classList.remove("open");
        if (mobileNavOverlay) mobileNavOverlay.classList.remove("active");
    }

    const btnBurger = $("#btn-burger");
    if (btnBurger) {
        btnBurger.addEventListener("click", () => {
            sidebarEl.classList.toggle("open");
            mobileNavOverlay.classList.toggle("active");
        });
    }
    if (mobileNavOverlay) {
        mobileNavOverlay.addEventListener("click", closeMobileNav);
    }

    // ─── Tabs ────────────────────────────────────────────────────────────────
    $$(".nav-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            $$(".nav-btn").forEach((b) => b.classList.remove("active"));
            btn.classList.add("active");
            $$(".tab-content").forEach((t) => t.classList.remove("active"));
            $(`#tab-${btn.dataset.tab}`).classList.add("active");

            const tab = btn.dataset.tab;
            if (tab === "dashboard") loadDashboard();
            if (tab === "suggestions") loadSuggestions();
            if (tab === "quiz") loadQuizTopics();
            if (tab === "challenge") loadChallenge();
            if (tab === "leaderboard") loadLeaderboard();
            if (tab === "profil") loadProfile();

            closeMobileNav();
        });
    });

    const btnQuickLog = $("#btn-quick-log");
    if (btnQuickLog) {
        btnQuickLog.addEventListener("click", () => {
            const logBtn = $(".nav-btn[data-tab='log']");
            if (logBtn) logBtn.click();
        });
    }

    // ─── Dashboard ───────────────────────────────────────────────────────────
    async function loadDashboard() {
        try {
            const [stats, badges, history, profile] = await Promise.all([
                api("/stats"),
                api("/badges"),
                api("/history?limit=5"),
                api("/profile"),
            ]);
            renderStats(stats);
            renderBadges(badges);
            renderHistory(history);
            renderProfileCta(profile);
        } catch (e) {
            toast(e.message, "error");
        }
    }

    function renderProfileCta(d) {
        const cta = $("#profile-cta");
        if (!cta) return;
        const pct = d?.completion || 0;
        if (pct >= 100) {
            cta.classList.add("hidden");
            return;
        }
        $("#profile-cta-sub").textContent =
            `Profil complété à ${pct}% — plus il est complet, plus les quiz, les idées et les conseils de l'IA te correspondent.`;
        $("#profile-cta-bar").style.width = pct + "%";
        cta.classList.remove("hidden");
    }

    const btnProfileCta = $("#btn-profile-cta");
    if (btnProfileCta) {
        btnProfileCta.addEventListener("click", () => {
            const profilBtn = $(".nav-btn[data-tab='profil']");
            if (profilBtn) profilBtn.click();
        });
    }

    function getLevelTitle(level) {
        if (level <= 2) return "Débutant";
        if (level <= 5) return "Apprenti";
        if (level <= 10) return "Confirmé";
        if (level <= 20) return "Expert";
        return "Maître";
    }

    function renderStats(s) {
        const totalMin = s.total_minutes || 0;
        const h = Math.floor(totalMin / 60);
        const m = totalMin % 60;

        // Streak card
        if ($("#s-streak")) $("#s-streak").textContent = s.current_streak;
        if ($("#s-streak-delta")) $("#s-streak-delta").textContent = `Meilleur : ${s.longest_streak} j`;

        // Points card
        if ($("#s-points")) $("#s-points").textContent = s.total_points.toLocaleString();
        if ($("#s-points-delta")) $("#s-points-delta").textContent = `Niveau ${s.level}`;

        // Level card
        if ($("#s-level")) $("#s-level").textContent = s.level;
        const nextLevelPoints = (s.level + 1) * (s.level + 1) * 100;
        const currentLevelPoints = s.level * s.level * 100;
        const ptsToNext = Math.max(0, nextLevelPoints - s.total_points);
        if ($("#s-level-pts")) $("#s-level-pts").textContent = `${ptsToNext} pts pour niv. ${s.level + 1}`;

        // Time card
        if (h > 0) {
            if (m > 0) {
                if ($("#s-time-val")) $("#s-time-val").textContent = `${h}h${m}`;
                if ($("#s-time-unit")) $("#s-time-unit").textContent = "";
            } else {
                if ($("#s-time-val")) $("#s-time-val").textContent = h;
                if ($("#s-time-unit")) $("#s-time-unit").textContent = "h";
            }
        } else {
            if ($("#s-time-val")) $("#s-time-val").textContent = m;
            if ($("#s-time-unit")) $("#s-time-unit").textContent = "min";
        }
        if ($("#s-sessions-sub")) {
            const n = s.total_sessions;
            $("#s-sessions-sub").textContent = `${n} session${n !== 1 ? "s" : ""}`;
        }

        // Badge counter
        if ($("#badge-counter")) $("#badge-counter").textContent = `${s.badge_count} / ${s.total_badges} collectés`;

        // Level progress section
        const range = nextLevelPoints - currentLevelPoints;
        const earned = s.total_points - currentLevelPoints;
        const progress = Math.min(100, Math.max(0, (earned / range) * 100));
        if ($("#level-progress")) $("#level-progress").style.width = `${progress}%`;
        if ($("#level-label")) $("#level-label").textContent = `Niv. ${s.level} · ${getLevelTitle(s.level)}`;
        if ($("#level-pts-current")) $("#level-pts-current").textContent = `${s.total_points.toLocaleString()} pts`;
        if ($("#level-pts-diff")) $("#level-pts-diff").textContent = `${ptsToNext.toLocaleString()} pts`;
        if ($("#level-sub-text")) {
            $("#level-sub-text").textContent = `${Math.max(0, earned).toLocaleString()} / ${range.toLocaleString()} pts pour atteindre le niveau ${s.level + 1}`;
        }

        renderMilestones(s.level);

        // Top subjects
        const cont = $("#top-subjects");
        if (!cont) return;
        if (!s.top_subjects || !s.top_subjects.length) {
            cont.innerHTML = '<p style="color:var(--text-muted);font-size:.88rem;padding:.5rem 0">Aucun sujet encore</p>';
            return;
        }
        const barColors = ["bar-green", "bar-blue", "bar-orange", "bar-purple", "bar-pink"];
        const max = s.top_subjects[0].count;
        cont.innerHTML = s.top_subjects.map((t, i) => `
            <div class="subject-row">
                <span class="subject-name">${esc(t.subject)}</span>
                <div class="subject-bar-track">
                    <div class="subject-bar-fill ${barColors[i % barColors.length]}" style="width:${(t.count / max) * 100}%"></div>
                </div>
                <span class="subject-duration">${t.count}</span>
            </div>`).join("");
    }

    function renderMilestones(currentLevel) {
        const cont = $("#level-milestones");
        if (!cont) return;
        const start = Math.max(1, currentLevel - 2);
        const end = start + 7;
        const items = [];
        for (let lvl = start; lvl <= end; lvl++) {
            let dotCls = "milestone-dot";
            let lblCls = "milestone-label";
            if (lvl < currentLevel) dotCls += " done";
            else if (lvl === currentLevel) { dotCls += " current"; lblCls += " current"; }
            items.push(`<div class="milestone">
                <div class="${dotCls}"></div>
                <span class="${lblCls}">${lvl}</span>
            </div>`);
        }
        cont.innerHTML = items.join("");
    }

    function renderBadges(b) {
        const grid = $("#badges-grid");
        if (!grid) return;

        // Extract leading emoji and remaining label from names like "🌱 Premier Pas"
        const splitBadge = (name) => {
            const idx = name.indexOf(" ");
            if (idx < 0) return { icon: name, label: name };
            return { icon: name.slice(0, idx), label: name.slice(idx + 1) };
        };

        // Deduplicate earned badges by name (guards against pre-existing duplicate DB rows)
        const seen = new Set();
        const earned = b.earned.filter((x) => {
            if (seen.has(x.name)) return false;
            seen.add(x.name);
            return true;
        });

        const earnedHtml = earned.map((x) => {
            const { icon, label } = splitBadge(x.name);
            return `<div class="badge-card-v2">
                <span class="badge-emoji">${icon}</span>
                <div class="badge-name">${esc(label)}</div>
                <div class="badge-desc">${esc(x.description)}</div>
            </div>`;
        }).join("");

        const lockedHtml = b.locked.map((x) => {
            const { label } = splitBadge(x.name);
            return `<div class="badge-card-v2 locked-badge">
                <span class="badge-emoji">🔒</span>
                <div class="badge-name">${esc(label)}</div>
                <div class="badge-desc">${esc(x.description)}</div>
            </div>`;
        }).join("");

        grid.innerHTML = earnedHtml + lockedHtml;
    }

    function renderHistory(list) {
        const cont = $("#history-list");
        if (!cont) return;
        if (!list.length) {
            cont.innerHTML = '<p style="color:var(--text-muted);font-size:.88rem;padding:.5rem 0">Aucune session encore</p>';
            return;
        }
        const iconColors = ["#16a34a", "#2563eb", "#ea580c", "#7c3aed", "#db2777"];
        cont.innerHTML = list.map((l, i) => {
            const d = new Date(l.date);
            const fmt = d.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit" });
            const color = iconColors[i % iconColors.length];
            return `<div class="activity-item">
                <div class="activity-icon" style="background:${color}20">📖</div>
                <div class="activity-text">
                    <div class="activity-title">${esc(l.subject)}</div>
                    <div class="activity-sub">${fmt}${l.description ? " · " + esc(l.description.slice(0, 45)) : ""}</div>
                </div>
                <div class="activity-meta">
                    <span class="activity-duration">${l.duration}min</span>
                    <span class="activity-pts">+${l.points}</span>
                </div>
            </div>`;
        }).join("");
    }

    // ─── Interests ───────────────────────────────────────────────────────────
    function renderTags(list) {
        currentInterests = list;
        const container = $("#interests-tags");
        if (!container) return;
        container.innerHTML = list.map((t) =>
            `<span class="interest-tag">${esc(t)}<button class="tag-x" data-topic="${esc(t)}" title="Supprimer">×</button></span>`
        ).join("");
        container.querySelectorAll(".tag-x").forEach((btn) => {
            btn.addEventListener("click", async () => {
                const topic = btn.dataset.topic;
                try {
                    const d = await api(`/interests/${encodeURIComponent(topic)}`, { method: "DELETE" });
                    renderTags(d.interests);
                    renderSubjectPills(d.interests);
                    refreshProfileDomains();
                    toast(`"${topic}" supprimé`, "success");
                } catch (e) {
                    toast(e.message, "error");
                }
            });
        });
    }

    function renderSubjectPills(interests) {
        const cont = $("#subject-pills");
        if (!cont) return;
        cont.innerHTML = interests.slice(0, 8).map((t) =>
            `<button class="subject-pill" data-subject="${esc(t)}">${esc(t)}</button>`
        ).join("");
        cont.querySelectorAll(".subject-pill").forEach((btn) => {
            btn.addEventListener("click", () => {
                cont.querySelectorAll(".subject-pill").forEach((b) => b.classList.remove("selected"));
                btn.classList.add("selected");
                const subjectInput = $("#log-subject");
                if (subjectInput) subjectInput.value = btn.dataset.subject;
                updateLogPreview();
            });
        });
    }

    const linkInterestsEdit = $("#link-interests-edit");
    const interestsEditPanel = $("#interests-edit-panel");
    if (linkInterestsEdit && interestsEditPanel) {
        linkInterestsEdit.addEventListener("click", () => {
            interestsEditPanel.classList.toggle("hidden");
            linkInterestsEdit.textContent = interestsEditPanel.classList.contains("hidden") ? "Modifier" : "Fermer";
        });
    }

    $("#btn-interests").addEventListener("click", async () => {
        const raw = $("#interests-input").value.trim();
        if (!raw) return;
        try {
            const d = await api("/interests", {
                method: "POST",
                body: JSON.stringify({ interests: raw }),
            });
            renderTags(d.interests);
            renderSubjectPills(d.interests);
            refreshProfileDomains();
            $("#interests-input").value = "";
            toast("Centres d'intérêt sauvegardés ✅", "success");
        } catch (e) {
            toast(e.message, "error");
        }
    });

    // ─── Duration buttons ─────────────────────────────────────────────────────
    $$(".duration-btn").forEach((btn) => {
        if (btn.id === "btn-duration-other") return;
        btn.addEventListener("click", () => {
            $$(".duration-btn").forEach((b) => b.classList.remove("selected"));
            btn.classList.add("selected");
            const dur = $("#log-duration");
            if (dur) {
                dur.value = btn.dataset.min;
                hide(dur);
            }
            const lbl = $("#duration-selected-label");
            if (lbl) lbl.textContent = btn.textContent;
            updateLogPreview();
        });
    });

    const btnDurationOther = $("#btn-duration-other");
    if (btnDurationOther) {
        btnDurationOther.addEventListener("click", () => {
            $$(".duration-btn").forEach((b) => b.classList.remove("selected"));
            btnDurationOther.classList.add("selected");
            const dur = $("#log-duration");
            if (dur) {
                dur.value = "";
                show(dur);
                dur.focus();
            }
            const lbl = $("#duration-selected-label");
            if (lbl) lbl.textContent = "Durée personnalisée";
        });
    }

    const logDurationInput = $("#log-duration");
    if (logDurationInput) {
        logDurationInput.addEventListener("input", updateLogPreview);
    }

    // ─── Char counter ─────────────────────────────────────────────────────────
    const logDesc = $("#log-desc");
    const descCounter = $("#desc-counter");
    if (logDesc && descCounter) {
        logDesc.addEventListener("input", () => {
            descCounter.textContent = `${logDesc.value.length} / 280`;
            updateLogPreview();
        });
    }

    // ─── Log preview ─────────────────────────────────────────────────────────
    function updateLogPreview() {
        const preview = $("#log-preview");
        if (!preview) return;
        const subject = ($("#log-subject") || {}).value || "";
        const duration = parseInt(($("#log-duration") || {}).value) || 0;
        if (!subject.trim() || !duration) {
            preview.textContent = "Prêt à enregistrer";
            return;
        }
        let pts = duration;
        if (duration >= 60) pts = Math.round(duration * 2);
        else if (duration >= 30) pts = Math.round(duration * 1.5);
        preview.textContent = `~${pts} pts estimés · ${subject}`;
    }

    const logSubjectInput = $("#log-subject");
    if (logSubjectInput) {
        logSubjectInput.addEventListener("input", updateLogPreview);
    }

    // ─── Log Session ─────────────────────────────────────────────────────────
    $("#btn-log").addEventListener("click", async () => {
        const subject = $("#log-subject").value.trim();
        const duration = $("#log-duration").value;
        const description = $("#log-desc").value.trim();
        if (!subject || !duration) {
            toast("Sujet et durée requis", "error");
            return;
        }
        const btn = $("#btn-log");
        btn.disabled = true;
        try {
            const d = await api("/log", {
                method: "POST",
                body: JSON.stringify({ subject, duration: parseInt(duration), description }),
            });
            const box = $("#log-result");
            box.classList.remove("hidden", "error");
            box.textContent = `✅ Session enregistrée !\n\n📚 Sujet : ${d.subject}\n⏱️ Durée : ${d.duration} min\n🎯 Points gagnés : +${d.points_earned}\n🔥 Streak : ${d.streak} jour(s)\n📊 Niveau : ${d.level}\n💰 Total : ${d.total_points} pts` +
                (d.new_badges.length ? `\n\n🏆 Nouveaux badges !\n${d.new_badges.map((b) => `${b.name} – ${b.description}`).join("\n")}` : "");

            $("#log-subject").value = "";
            $("#log-duration").value = "";
            hide($("#log-duration"));
            if (logDesc) logDesc.value = "";
            if (descCounter) descCounter.textContent = "0 / 280";
            $$(".duration-btn").forEach((b) => b.classList.remove("selected"));
            $$(".subject-pill").forEach((b) => b.classList.remove("selected"));
            const lbl = $("#duration-selected-label");
            if (lbl) lbl.textContent = "";
            const preview = $("#log-preview");
            if (preview) preview.textContent = "Prêt à enregistrer";
            toast(`+${d.points_earned} points ! 🔥`, "success");
        } catch (e) {
            const box = $("#log-result");
            box.classList.remove("hidden");
            box.classList.add("error");
            box.textContent = e.message;
        } finally {
            btn.disabled = false;
        }
    });

    // ─── Suggest (Logger panel) ───────────────────────────────────────────────
    const btnSuggest = $("#btn-suggest");
    if (btnSuggest) {
        btnSuggest.addEventListener("click", async () => {
            btnSuggest.disabled = true;
            btnSuggest.textContent = "⏳ Réflexion...";
            try {
                const d = await api("/suggest");
                const text = d.suggestion || "";
                const lines = text.split("\n").filter(Boolean);
                const titleEl = $("#suggest-title-text");
                const descEl = $("#suggest-desc-text");
                if (titleEl) titleEl.innerHTML = mdToHtml(lines[0] || text);
                if (descEl) descEl.innerHTML = lines.length > 1
                    ? lines.slice(1).filter(Boolean).map(mdToHtml).join("<br>")
                    : "Basé sur tes centres d'intérêt et ta progression.";
                hide($("#suggest-result"));
            } catch (e) {
                const box = $("#suggest-result");
                show(box);
                box.classList.add("error");
                box.textContent = e.message;
            } finally {
                btnSuggest.disabled = false;
                btnSuggest.textContent = "✨ Obtenir une suggestion";
            }
        });
    }

    // ─── Générateur d'idées (onglet Suggestions) ────────────────────────────
    let ideaState = { clarified: "", questions: [] };

    function ideaHtml(text) {
        return text.split("\n").map(mdToHtml).join("<br>");
    }

    function ideaUpdatePlaceholder() {
        const ph = $("#idea-placeholder");
        if (!ph) return;
        const busy = !$("#idea-loading").classList.contains("hidden") ||
            !$("#idea-step-result").classList.contains("hidden");
        ph.classList.toggle("hidden", busy);
    }

    function ideaLoading(on, caption) {
        const box = $("#idea-loading");
        if (caption) $("#idea-loading-caption").textContent = caption;
        box.classList.toggle("hidden", !on);
        ideaUpdatePlaceholder();
    }

    function ideaShowStep(id) {
        ["idea-step-questions", "idea-step-clarified", "idea-step-result"].forEach((s) => {
            $("#" + s).classList.toggle("hidden", s !== id);
        });
        ideaUpdatePlaceholder();
    }

    async function loadSuggestions() {
        try {
            const d = await api("/profile");
            const p = d.profile || {};
            $("#idea-skills").value = p.skills_resources || "";
            $("#idea-time").value = p.time_available || "";
            $("#idea-personality").value = p.personality || "";
            $("#idea-constraints").value = p.constraints || "";
            $("#idea-location").value = p.location || "";
            ideaState.clarified = p.clarified_profile || "";
            $("#btn-idea-direct").classList.toggle("hidden", !ideaState.clarified);
            $("#idea-clarified-hint").textContent = ideaState.clarified
                ? "Ton profil a déjà été clarifié — tu peux générer directement, ou re-clarifier après modification."
                : "";
        } catch (e) {
            toast(e.message, "error");
        }
    }

    async function saveIdeaProfile() {
        await api("/profile", {
            method: "PUT",
            body: JSON.stringify({
                skills_resources: $("#idea-skills").value.trim(),
                time_available: $("#idea-time").value.trim(),
                personality: $("#idea-personality").value.trim(),
                constraints: $("#idea-constraints").value.trim(),
                location: $("#idea-location").value.trim(),
            }),
        });
    }

    function ideaShowClarified(text) {
        ideaState.clarified = text;
        $("#idea-clarified-text").innerHTML = ideaHtml(text);
        $("#idea-correction").value = "";
        ideaShowStep("idea-step-clarified");
    }

    $$("#idea-type .quiz-pill").forEach((btn) => {
        btn.addEventListener("click", () => {
            $$("#idea-type .quiz-pill").forEach((b) => b.classList.remove("selected"));
            btn.classList.add("selected");
        });
    });

    $("#btn-idea-clarify").addEventListener("click", async () => {
        try {
            ideaShowStep(null);
            ideaLoading(true, "Analyse de ton profil par l'IA...");
            await saveIdeaProfile();
            const d = await api("/idea/clarify", { method: "POST", body: "{}" });
            ideaLoading(false);
            if (d.questions && d.questions.length) {
                ideaState.questions = d.questions;
                $("#idea-questions-list").innerHTML = d.questions.map((q, i) => `
                    <div class="form-section">
                        <label class="form-label">${esc(q)}</label>
                        <input type="text" class="idea-answer" data-q="${esc(q)}" maxlength="300" placeholder="Ta réponse (optionnelle)">
                    </div>`).join("");
                ideaShowStep("idea-step-questions");
            } else if (d.clarified) {
                ideaShowClarified(d.clarified);
            }
        } catch (e) {
            ideaLoading(false);
            toast(e.message, "error");
        }
    });

    $("#btn-idea-answers").addEventListener("click", async () => {
        const answers = [...$$(".idea-answer")].map((inp) => ({ q: inp.dataset.q, a: inp.value.trim() }));
        try {
            ideaShowStep(null);
            ideaLoading(true, "Synthèse de ton profil clarifié...");
            const d = await api("/idea/clarify", { method: "POST", body: JSON.stringify({ answers }) });
            ideaLoading(false);
            ideaShowClarified(d.clarified);
        } catch (e) {
            ideaLoading(false);
            toast(e.message, "error");
        }
    });

    $("#btn-idea-refine").addEventListener("click", async () => {
        const correction = $("#idea-correction").value.trim();
        if (!correction) {
            toast("Écris d'abord ta correction", "error");
            return;
        }
        try {
            ideaLoading(true, "Application de ta correction...");
            const d = await api("/idea/refine", {
                method: "POST",
                body: JSON.stringify({ clarified: ideaState.clarified, correction }),
            });
            ideaLoading(false);
            ideaShowClarified(d.clarified);
        } catch (e) {
            ideaLoading(false);
            toast(e.message, "error");
        }
    });

    async function ideaGenerate() {
        const ideaType = $("#idea-type .selected")?.dataset.val || "les_deux";
        try {
            ideaShowStep(null);
            ideaLoading(true, "Génération de ton idée personnalisée...");
            const d = await api("/idea/generate", { method: "POST", body: JSON.stringify({ idea_type: ideaType }) });
            ideaLoading(false);
            $("#idea-result-text").innerHTML = ideaHtml(d.idea);
            const evalBox = $("#idea-eval-details");
            if (d.evaluation) {
                $("#idea-eval-text").innerHTML = ideaHtml(d.evaluation);
                evalBox.classList.remove("hidden");
                evalBox.open = false;
            } else {
                evalBox.classList.add("hidden");
            }
            ideaShowStep("idea-step-result");
            $("#btn-idea-direct").classList.remove("hidden");
        } catch (e) {
            ideaLoading(false);
            toast(e.message, "error");
        }
    }

    $("#btn-idea-validate").addEventListener("click", async () => {
        try {
            await api("/idea/validate", { method: "POST", body: JSON.stringify({ clarified: ideaState.clarified }) });
            $("#idea-clarified-hint").textContent = "Ton profil a déjà été clarifié — tu peux générer directement, ou re-clarifier après modification.";
            await ideaGenerate();
        } catch (e) {
            toast(e.message, "error");
        }
    });

    $("#btn-idea-direct").addEventListener("click", ideaGenerate);
    $("#btn-idea-regen").addEventListener("click", ideaGenerate);

    $("#btn-idea-restart").addEventListener("click", () => {
        ideaShowStep(null);
        $("#idea-step-profile").scrollIntoView({ behavior: "smooth" });
    });

    // ─── Challenge ───────────────────────────────────────────────────────────
    async function loadChallenge() {
        show($("#challenge-loading"));
        hide($("#challenge-content"));
        try {
            const d = await api("/challenge");
            const dateEl = $("#challenge-date");
            if (dateEl) {
                const now = new Date();
                const dateStr = now.toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" });
                const midnight = new Date(now);
                midnight.setHours(24, 0, 0, 0);
                const msLeft = midnight - now;
                const hoursLeft = Math.floor(msLeft / 3600000);
                const minsLeft = Math.floor((msLeft % 3600000) / 60000);
                const countdown = hoursLeft > 0 ? `Renouvellement dans ${hoursLeft}h` : `Renouvellement dans ${minsLeft} min`;
                dateEl.innerHTML = `📅 ${dateStr} <span style="opacity:.7">— ${countdown}</span>`;
            }
            if ($("#challenge-title")) $("#challenge-title").textContent = d.title;
            if ($("#challenge-cat")) {
                const cat = d.category ? d.category.charAt(0).toUpperCase() + d.category.slice(1) : "";
                $("#challenge-cat").textContent = cat;
            }
            if ($("#challenge-explanation")) $("#challenge-explanation").textContent = d.explanation || "";
            hide($("#challenge-loading"));
            show($("#challenge-content"));
        } catch (e) {
            hide($("#challenge-loading"));
            toast(e.message, "error");
        }
    }

    const btnChallengeLog = $("#btn-challenge-log");
    if (btnChallengeLog) {
        btnChallengeLog.addEventListener("click", () => {
            const logBtn = $(".nav-btn[data-tab='log']");
            if (logBtn) logBtn.click();
        });
    }

    const btnReloadChallenge = $("#btn-reload-challenge");
    if (btnReloadChallenge) {
        btnReloadChallenge.addEventListener("click", loadChallenge);
    }

    // ─── Leaderboard ─────────────────────────────────────────────────────────
    const lbBtnWeek = $("#lb-btn-week");
    const lbBtnAll = $("#lb-btn-all");

    if (lbBtnWeek) {
        lbBtnWeek.addEventListener("click", () => {
            lbPeriod = "week";
            lbBtnWeek.classList.add("active");
            if (lbBtnAll) lbBtnAll.classList.remove("active");
            const sub = $("#lb-subtitle");
            if (sub) sub.textContent = "Top apprenants de cette semaine";
            loadLeaderboard();
        });
    }
    if (lbBtnAll) {
        lbBtnAll.addEventListener("click", () => {
            lbPeriod = "all";
            lbBtnAll.classList.add("active");
            if (lbBtnWeek) lbBtnWeek.classList.remove("active");
            const sub = $("#lb-subtitle");
            if (sub) sub.textContent = "Top apprenants de la communauté";
            loadLeaderboard();
        });
    }

    async function loadLeaderboard() {
        try {
            const endpoint = lbPeriod === "week" ? "/leaderboard?period=week" : "/leaderboard";
            const list = await api(endpoint);
            const cont = $("#leaderboard-list");
            if (!list.length) {
                cont.innerHTML = '<p style="color:var(--text-muted);padding:.5rem 0">Aucun apprenant encore</p>';
                return;
            }
            const avatarColors = ["#16a34a", "#2563eb", "#ea580c", "#7c3aed", "#db2777", "#0891b2", "#d97706"];
            const rankHtml = (i) => {
                if (i === 0) return `<span class="rank-badge rank-1">🥇</span>`;
                if (i === 1) return `<span class="rank-badge rank-2">🥈</span>`;
                if (i === 2) return `<span class="rank-badge rank-3">🥉</span>`;
                return `<span class="rank-other">${i + 1}</span>`;
            };
            cont.innerHTML = `
                <table class="lb-table">
                    <thead class="lb-thead">
                        <tr>
                            <th>#</th>
                            <th>Apprenant</th>
                            <th>Niveau</th>
                            <th>Streak</th>
                            <th>Points</th>
                        </tr>
                    </thead>
                    <tbody class="lb-tbody">
                        ${list.map((u, i) => {
                            const color = avatarColors[i % avatarColors.length];
                            const initials = u.username.slice(0, 2).toUpperCase();
                            const isMe = u.username === currentUser;
                            return `<tr${isMe ? ' class="me-row"' : ""}>
                                <td><div class="lb-rank-cell">${rankHtml(i)}</div></td>
                                <td>
                                    <div class="lb-user-cell">
                                        <div class="lb-avatar" style="background:${color}">${initials}</div>
                                        <span class="lb-username">${esc(u.username)}${isMe ? '<span class="lb-me-tag">(toi)</span>' : ""}</span>
                                    </div>
                                </td>
                                <td class="lb-level">Niv. ${u.level}</td>
                                <td class="lb-streak">${u.streak} 🔥</td>
                                <td class="lb-points">${u.points.toLocaleString()}</td>
                            </tr>`;
                        }).join("")}
                    </tbody>
                </table>`;
        } catch (e) {
            toast(e.message, "error");
        }
    }

    // ─── Quiz ────────────────────────────────────────────────────────────────
    let quizState = { questions: [], topic: "", currentQ: 0, score: 0, correctQuestions: [] };

    // Suggestions de sujets adaptées au profil
    let quizTopicsLoaded = false;
    let quizTopicsList = [];

    async function loadQuizTopics(force = false) {
        const box = $("#quiz-topic-suggestions");
        if (!box || (quizTopicsLoaded && !force)) return;
        box.innerHTML = '<span class="quiz-suggest-status">Chargement des suggestions…</span>';
        try {
            const d = await api("/quiz/topics");
            quizTopicsLoaded = true;
            quizTopicsList = d.suggestions || [];
            if (!quizTopicsList.length) {
                box.innerHTML = '<span class="quiz-suggest-status">Complète ton profil pour recevoir des suggestions.</span>';
                return;
            }
            box.innerHTML = quizTopicsList.map((s, i) =>
                `<button type="button" class="quiz-pill quiz-topic-pill" data-idx="${i}" title="${esc(s.why || "")}">${esc(s.topic)}</button>`
            ).join("");
            box.querySelectorAll(".quiz-topic-pill").forEach((btn) => {
                btn.addEventListener("click", () => {
                    box.querySelectorAll(".quiz-topic-pill").forEach((b) => b.classList.remove("selected"));
                    btn.classList.add("selected");
                    $("#quiz-topic").value = quizTopicsList[btn.dataset.idx].topic;
                });
            });
        } catch (e) {
            box.innerHTML = `<span class="quiz-suggest-status">${esc(e.message)}</span>`;
        }
    }

    const btnQuizSuggestRefresh = $("#btn-quiz-suggest-refresh");
    if (btnQuizSuggestRefresh) btnQuizSuggestRefresh.addEventListener("click", () => loadQuizTopics(true));

    const quizTopicInput = $("#quiz-topic");
    if (quizTopicInput) {
        quizTopicInput.addEventListener("input", () => {
            $$("#quiz-topic-suggestions .quiz-topic-pill").forEach((b) => b.classList.remove("selected"));
        });
    }

    ["#quiz-size", "#quiz-difficulty", "#quiz-type", "#quiz-numopts"].forEach((sel) => {
        $$(sel + " [data-val]").forEach((btn) => {
            btn.addEventListener("click", () => {
                $$(sel + " [data-val]").forEach((b) => b.classList.remove("selected"));
                btn.classList.add("selected");
                if (sel === "#quiz-type") {
                    const isVF = btn.dataset.val === "vrai_faux";
                    $("#quiz-numopts-section").classList.toggle("hidden", isVF);
                    $("#quiz-multi-section").classList.toggle("hidden", isVF);
                }
            });
        });
    });

    $("#btn-quiz-start").addEventListener("click", async () => {
        const topic = $("#quiz-topic").value.trim();
        hide($("#quiz-start"));
        show($("#quiz-loading"));
        hide($("#quiz-result"));
        hide($("#quiz-game"));
        try {
            const d = await api("/quiz/generate", {
                method: "POST",
                body: JSON.stringify({
                    topic,
                    size: $("#quiz-size .selected").dataset.val,
                    difficulty: $("#quiz-difficulty .selected").dataset.val,
                    qcm_type: $("#quiz-type .selected").dataset.val,
                    num_options: parseInt($("#quiz-numopts .selected").dataset.val),
                    multi: $("#quiz-multi").checked,
                }),
            });
            quizState = { questions: d.questions, topic: d.topic, currentQ: 0, score: 0, correctQuestions: [] };
            hide($("#quiz-loading"));
            show($("#quiz-game"));
            renderQuestion();
        } catch (e) {
            hide($("#quiz-loading"));
            show($("#quiz-start"));
            toast(e.message, "error");
        }
    });

    function renderQuestion() {
        const q = quizState.questions[quizState.currentQ];
        const total = quizState.questions.length;
        const i = quizState.currentQ;
        const pct = (i / total) * 100;
        const letters = ["A", "B", "C", "D", "E", "F", "G"];
        const isMulti = Array.isArray(q.correct);

        $("#quiz-game").innerHTML = `
            <div class="quiz-header-bar">
                <span class="quiz-q-label">Q${i + 1}/${total}</span>
                <div class="quiz-progress-track">
                    <div class="quiz-progress-fill" style="width:${pct}%"></div>
                </div>
                <span class="quiz-subject-label">${esc(quizState.topic)}</span>
            </div>
            <p class="quiz-question-text">${esc(q.question)}</p>
            ${isMulti ? '<p class="page-subtitle" style="margin-bottom:.75rem">Plusieurs réponses possibles — sélectionne puis valide.</p>' : ""}
            <div class="quiz-options-v2">
                ${q.options.map((o, idx) => `
                    <button class="quiz-option-v2" data-idx="${idx}">
                        <span class="quiz-opt-letter">${letters[idx] || idx + 1}</span>
                        <span class="quiz-opt-text">${esc(o)}</span>
                    </button>`).join("")}
            </div>
            ${isMulti ? '<button class="btn btn-primary" id="btn-quiz-validate" style="margin-top:.85rem">Valider mes réponses</button>' : ""}
            <div id="quiz-feedback" class="hidden"></div>`;

        if (isMulti) {
            $$(".quiz-option-v2").forEach((btn) => {
                btn.addEventListener("click", () => btn.classList.toggle("multi-selected"));
            });
            $("#btn-quiz-validate").addEventListener("click", handleMultiAnswer);
        } else {
            $$(".quiz-option-v2").forEach((btn) => {
                btn.addEventListener("click", () => handleAnswer(parseInt(btn.dataset.idx)));
            });
        }
    }

    function handleAnswer(idx) {
        const q = quizState.questions[quizState.currentQ];
        const options = $$(".quiz-option-v2");
        options.forEach((btn) => {
            btn.disabled = true;
            const bIdx = parseInt(btn.dataset.idx);
            if (bIdx === q.correct) btn.classList.add("correct");
            if (bIdx === idx && idx !== q.correct) btn.classList.add("wrong");
        });
        concludeQuestion(idx === q.correct, q);
    }

    function handleMultiAnswer() {
        const q = quizState.questions[quizState.currentQ];
        const correctSet = new Set(q.correct);
        const options = $$(".quiz-option-v2");
        const selected = new Set(
            [...options].filter((b) => b.classList.contains("multi-selected")).map((b) => parseInt(b.dataset.idx))
        );
        if (selected.size === 0) {
            toast("Sélectionne au moins une réponse", "error");
            return;
        }
        const ok = selected.size === correctSet.size && [...selected].every((i) => correctSet.has(i));
        options.forEach((btn) => {
            btn.disabled = true;
            btn.classList.remove("multi-selected");
            const bIdx = parseInt(btn.dataset.idx);
            if (correctSet.has(bIdx)) btn.classList.add("correct");
            else if (selected.has(bIdx)) btn.classList.add("wrong");
        });
        const validateBtn = $("#btn-quiz-validate");
        if (validateBtn) validateBtn.remove();
        concludeQuestion(ok, q);
    }

    function concludeQuestion(ok, q) {
        if (ok) {
            quizState.score++;
            quizState.correctQuestions.push(q.question);
        }

        const feedback = $("#quiz-feedback");
        show(feedback);
        if (q.explanation) {
            feedback.innerHTML = `<div class="quiz-explanation-v2">💡 ${esc(q.explanation)}</div>`;
        }

        const isLast = quizState.currentQ >= quizState.questions.length - 1;
        const footer = document.createElement("div");
        footer.className = "quiz-footer";
        footer.innerHTML = `
            <span class="quiz-score-label">Score : <span class="pts">${quizState.score}/${quizState.currentQ + 1}</span></span>
            <button class="btn btn-primary">${isLast ? "Voir les résultats" : "Question suivante →"}</button>`;
        footer.querySelector("button").addEventListener("click", () => {
            if (isLast) {
                submitQuiz();
            } else {
                quizState.currentQ++;
                renderQuestion();
            }
        });
        $("#quiz-game").appendChild(footer);
    }

    async function submitQuiz() {
        hide($("#quiz-game"));
        try {
            const d = await api("/quiz/submit", {
                method: "POST",
                body: JSON.stringify({
                    topic: quizState.topic,
                    score: quizState.score,
                    total: quizState.questions.length,
                    correct_questions: quizState.correctQuestions,
                }),
            });
            const box = $("#quiz-result");
            show(box);
            const badgeText = d.new_badges.length
                ? `<div style="margin-top:1rem"><strong>🏆 Nouveaux badges !</strong><br>${d.new_badges.map((b) => `${b.name} – ${b.description}`).join("<br>")}</div>`
                : "";
            box.innerHTML = `
                <div style="text-align:center;padding:1rem 0">
                    <p style="font-size:2.2rem;font-weight:900;letter-spacing:-.04em;margin-bottom:.5rem">${d.score}/${d.total}</p>
                    <p style="font-size:1.2rem;font-weight:700;color:${d.percentage >= 66 ? "var(--green)" : "var(--orange)"};margin-bottom:1rem">${d.percentage.toFixed(0)}%</p>
                    <div style="display:flex;justify-content:center;gap:1.5rem;flex-wrap:wrap;font-size:.9rem;color:var(--text-muted);margin-bottom:1rem">
                        <span>🎯 +${d.points_earned} pts</span>
                        <span>📊 Niveau ${d.level}</span>
                        <span>💰 ${d.total_points.toLocaleString()} pts</span>
                    </div>
                    ${badgeText}
                    <button class="btn btn-primary" style="margin-top:1rem" id="btn-quiz-again">🔄 Nouveau quiz</button>
                </div>`;
            $("#btn-quiz-again").addEventListener("click", () => {
                hide(box);
                show($("#quiz-start"));
            });
        } catch (e) {
            toast(e.message, "error");
            show($("#quiz-start"));
        }
    }

    // ─── Profil ──────────────────────────────────────────────────────────────
    const PF_LEVELS = ["débutant", "intermédiaire", "avancé"];

    $$("#pf-formats .quiz-pill").forEach((btn) => {
        btn.addEventListener("click", () => btn.classList.toggle("selected"));
    });

    function renderProfileDomains(levels) {
        const cont = $("#pf-domains");
        if (!currentInterests.length) {
            cont.innerHTML = '<p class="form-label-hint">Ajoute d\'abord des centres d\'intérêt ci-dessus pour évaluer ton niveau.</p>';
            return;
        }
        cont.innerHTML = currentInterests.map((it) => `
            <div class="pf-domain-row" data-domain="${esc(it)}">
                <span class="pf-domain-name">${esc(it)}</span>
                <div class="quiz-pills">
                    ${PF_LEVELS.map((l) => `<button type="button" class="quiz-pill pf-level ${levels[it] === l ? "selected" : ""}" data-val="${l}">${l}</button>`).join("")}
                </div>
            </div>`).join("");
        $$(".pf-domain-row").forEach((row) => {
            row.querySelectorAll(".pf-level").forEach((btn) => {
                btn.addEventListener("click", () => {
                    const wasSelected = btn.classList.contains("selected");
                    row.querySelectorAll(".pf-level").forEach((b) => b.classList.remove("selected"));
                    if (!wasSelected) btn.classList.add("selected");
                });
            });
        });
    }

    function refreshProfileDomains() {
        const levels = {};
        $$(".pf-domain-row").forEach((row) => {
            const sel = row.querySelector(".pf-level.selected");
            if (sel) levels[row.dataset.domain] = sel.dataset.val;
        });
        renderProfileDomains(levels);
    }

    function updateProfileCompletion(pct) {
        $("#pf-completion-pct").textContent = pct + "%";
        $("#pf-completion-bar").style.width = pct + "%";
    }

    async function loadProfile() {
        try {
            const d = await api("/profile");
            const p = d.profile || {};
            $("#pf-birth").value = p.birth_date || "";
            $("#pf-location").value = p.location || "";
            $("#pf-status").value = p.status || "";
            $("#pf-goal").value = p.goal || "";
            $("#pf-deadline").value = p.goal_deadline || "";
            $("#pf-languages").value = p.languages || "";
            $("#pf-bio").value = p.bio || "";
            $("#pf-skills").value = p.skills_resources || "";
            $("#pf-time").value = p.time_available || "";
            $("#pf-personality").value = p.personality || "";
            $("#pf-constraints").value = p.constraints || "";
            const formats = p.learning_formats || [];
            $$("#pf-formats .quiz-pill").forEach((b) => b.classList.toggle("selected", formats.includes(b.dataset.val)));
            renderProfileDomains(p.domain_levels || {});
            updateProfileCompletion(d.completion || 0);
        } catch (e) {
            toast(e.message, "error");
        }
    }

    $("#btn-profile-save").addEventListener("click", async () => {
        const domain_levels = {};
        $$(".pf-domain-row").forEach((row) => {
            const sel = row.querySelector(".pf-level.selected");
            if (sel) domain_levels[row.dataset.domain] = sel.dataset.val;
        });
        const body = {
            birth_date: $("#pf-birth").value,
            location: $("#pf-location").value.trim(),
            status: $("#pf-status").value,
            goal: $("#pf-goal").value,
            goal_deadline: $("#pf-deadline").value.trim(),
            languages: $("#pf-languages").value.trim(),
            bio: $("#pf-bio").value.trim(),
            skills_resources: $("#pf-skills").value.trim(),
            time_available: $("#pf-time").value.trim(),
            personality: $("#pf-personality").value.trim(),
            constraints: $("#pf-constraints").value.trim(),
            learning_formats: [...$$("#pf-formats .quiz-pill.selected")].map((b) => b.dataset.val),
            domain_levels,
        };
        try {
            const d = await api("/profile", { method: "PUT", body: JSON.stringify(body) });
            updateProfileCompletion(d.completion || 0);
            quizTopicsLoaded = false; // le profil a changé → nouvelles suggestions de quiz
            toast("Profil enregistré ✓", "success");
        } catch (e) {
            toast(e.message, "error");
        }
    });

    // ─── Chat ────────────────────────────────────────────────────────────────
    function appendChatMsg(container, type, text) {
        const isBot = type === "bot";
        const row = document.createElement("div");
        row.className = `chat-row${isBot ? "" : " user-row"}`;
        row.innerHTML = `
            <div class="chat-avatar ${isBot ? "bot-avatar" : "user-avatar-chat"}">${isBot ? "E" : getInitials(currentUser)}</div>
            <div class="chat-bubble ${isBot ? "bot-bubble" : "user-bubble"}">${esc(text)}</div>`;
        container.appendChild(row);
    }

    async function sendChat() {
        const input = $("#chat-input");
        const msg = input.value.trim();
        if (!msg) return;
        input.value = "";

        const container = $("#chat-messages");
        appendChatMsg(container, "user", msg);
        container.scrollTop = container.scrollHeight;

        try {
            const d = await api("/chat", {
                method: "POST",
                body: JSON.stringify({ message: msg }),
            });
            appendChatMsg(container, "bot", d.reply);
        } catch (e) {
            appendChatMsg(container, "bot", `❌ ${e.message}`);
        }
        container.scrollTop = container.scrollHeight;
    }

    $("#btn-chat-send").addEventListener("click", sendChat);
    $("#chat-input").addEventListener("keydown", (e) => {
        if (e.key === "Enter") sendChat();
    });

    $$(".chat-suggest-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            const input = $("#chat-input");
            if (input) input.value = btn.dataset.q;
            sendChat();
        });
    });

    // ─── Guided Tour ─────────────────────────────────────────────────────────
    const TOUR = [
        {
            sel: '.nav-btn[data-tab="dashboard"]', pos: "right",
            title: "Dashboard 📊",
            body: "Ta vue d'ensemble : série de jours, points, niveau, badges débloqués et historique récent. C'est ta page d'accueil.",
        },
        {
            sel: '.nav-btn[data-tab="suggestions"]', pos: "right",
            title: "Générateur d'idées 💡",
            body: "Décris ton profil (compétences, temps, personnalité, contraintes, zone géographique) : l'IA le clarifie avec toi, puis génère une idée entrepreneuriale ou éducative sur mesure, évaluée et régénérable.",
        },
        {
            sel: '#link-interests-edit', pos: "top", tab: "profil",
            title: "Centres d'intérêt ⚙️",
            body: "Configure tes sujets favoris ici (ex : Maths pour le Collège, Marketing). Plus tu es spécifique, plus les fonctionnalités IA s'adaptent avec précision à tes besoins.",
        },
        {
            sel: '.nav-btn[data-tab="log"]', pos: "right",
            title: "Logger une session 📝",
            body: "Après chaque apprentissage : clique ici → choisis le sujet et la durée → valide. Tu gagnes des points et ta série est protégée.",
        },
        {
            sel: '.nav-btn[data-tab="quiz"]', pos: "right",
            title: "Quiz IA 🎲",
            body: "Configure ton quiz (taille, difficulté, type de questions) et lance-le sur n'importe quel sujet, généré en temps réel. Les bonnes réponses rapportent des points bonus.",
        },
        {
            sel: '.nav-btn[data-tab="challenge"]', pos: "right",
            title: "Défi du Jour 🎯",
            body: "Un défi unique renouvelé chaque 24h. Relève-le pour sortir de ta zone de confort, gagner des points bonus et débloquer des badges.",
        },
        {
            sel: '.nav-btn[data-tab="leaderboard"]', pos: "right",
            title: "Classement 🏆",
            body: "Compare ta progression avec la communauté. Filtre par cette semaine ou par tous les temps.",
        },
        {
            sel: '.nav-btn[data-tab="chat"]', pos: "right",
            title: "Chat IA 💬",
            body: "Ton assistant personnel disponible 24h/24. Pose toutes tes questions, demande des explications ou un plan d'apprentissage sur mesure.",
        },
    ];

    let tourStep = 0;
    let tourPulseEl = null;
    let tourTransitioning = false;

    function tourIsMobile() { return window.innerWidth <= 640; }

    function startTour() {
        tourStep = 0;
        const tip = $("#tour-tip");
        if (tip) tip.classList.remove("hidden");
        showTourStep(0);
    }

    function endTour() {
        const tip = $("#tour-tip");
        if (tip) tip.classList.add("hidden");
        clearTourPulse();
        localStorage.setItem("earaka-tour-done", "1");
    }

    function clearTourPulse() {
        if (tourPulseEl) { tourPulseEl.classList.remove("tour-pulse"); tourPulseEl = null; }
    }

    function showTourStep(i) {
        const step = TOUR[i];
        const tip = $("#tour-tip");
        if (!tip || tourTransitioning) return;
        tourTransitioning = true;
        clearTourPulse();

        tip.style.opacity = "0";
        setTimeout(() => {
            // Update text
            $("#tour-step-lbl").textContent = `Étape ${i + 1} sur ${TOUR.length}`;
            $("#tour-tip-title").textContent = step.title;
            $("#tour-tip-body").textContent = step.body;
            const dotsEl = $("#tour-dots");
            dotsEl.innerHTML = TOUR.map((_, idx) =>
                `<span class="tour-dot${idx === i ? " on" : ""}"></span>`
            ).join("");
            const prevBtn = $("#btn-tour-prev");
            if (i === 0) prevBtn.classList.add("hidden"); else prevBtn.classList.remove("hidden");
            $("#btn-tour-next").textContent = i === TOUR.length - 1 ? "Terminer ✓" : "Suivant →";

            // Navigate to required tab first
            if (step.tab) {
                const tabBtn = $(`.nav-btn[data-tab="${step.tab}"]`);
                if (tabBtn && !tabBtn.classList.contains("active")) tabBtn.click();
            }

            // Reset positioning (preserve opacity:0)
            tip.removeAttribute("data-arrow");
            tip.style.left = "";
            tip.style.top = "";
            tip.style.transform = "";

            if (!tourIsMobile() && step.sel) {
                const target = $(step.sel);
                if (target) {
                    target.classList.add("tour-pulse");
                    tourPulseEl = target;
                    const r = target.getBoundingClientRect();
                    const inView = r.top >= 0 && r.bottom <= window.innerHeight;
                    const doPosition = () => {
                        positionTourTip(tip, target, step.pos);
                        tip.style.opacity = "1";
                        tourTransitioning = false;
                    };
                    if (!inView) {
                        target.scrollIntoView({ behavior: "smooth", block: "center" });
                        setTimeout(doPosition, 480);
                    } else {
                        requestAnimationFrame(doPosition);
                    }
                    return;
                }
            }
            // Mobile or no target → center
            tip.style.left = "50%";
            tip.style.top = "50%";
            tip.style.transform = "translate(-50%, -50%)";
            tip.style.opacity = "1";
            tourTransitioning = false;
        }, 160);
    }

    function positionTourTip(tip, target, pos) {
        const r = target.getBoundingClientRect();
        const vw = window.innerWidth;
        const vh = window.innerHeight;
        const tw = 300;
        const th = tip.offsetHeight || 210;
        const pad = 14;
        let left, top;

        if (pos === "right") {
            left = r.right + pad;
            top = r.top + r.height / 2 - th / 2;
            tip.setAttribute("data-arrow", "left");
        } else if (pos === "top") {
            left = r.left + r.width / 2 - tw / 2;
            top = r.top - th - pad;
            tip.setAttribute("data-arrow", "down");
        } else {
            left = r.left + r.width / 2 - tw / 2;
            top = r.bottom + pad;
            tip.setAttribute("data-arrow", "up");
        }
        left = Math.max(pad, Math.min(left, vw - tw - pad));
        top = Math.max(pad, Math.min(top, vh - th - pad));
        tip.style.left = `${left}px`;
        tip.style.top = `${top}px`;
    }

    const btnTourPrev = $("#btn-tour-prev");
    const btnTourNext = $("#btn-tour-next");
    const btnTourSkip = $("#btn-tour-skip");
    const btnTourClose = $("#btn-tour-close");
    if (btnTourPrev) btnTourPrev.addEventListener("click", () => { if (tourStep > 0) showTourStep(--tourStep); });
    if (btnTourNext) btnTourNext.addEventListener("click", () => { if (tourStep < TOUR.length - 1) showTourStep(++tourStep); else endTour(); });
    if (btnTourSkip) btnTourSkip.addEventListener("click", endTour);
    if (btnTourClose) btnTourClose.addEventListener("click", endTour);

    const btnShowTour = $("#btn-show-tour");
    const btnShowTourMobile = $("#btn-show-tour-mobile");
    if (btnShowTour) btnShowTour.addEventListener("click", startTour);
    if (btnShowTourMobile) btnShowTourMobile.addEventListener("click", startTour);

    // ─── Aide tab ─────────────────────────────────────────────────────────────
    const btnMobileAide = $("#btn-mobile-aide");
    if (btnMobileAide) btnMobileAide.addEventListener("click", () => {
        const aideBtn = $(".nav-btn[data-tab='aide']");
        if (aideBtn) aideBtn.click();
    });

    const btnAideTour = $("#btn-aide-tour");
    if (btnAideTour) btnAideTour.addEventListener("click", startTour);

    const aideInput = $("#aide-question-input");
    const aideCounter = $("#aide-char-counter");
    if (aideInput && aideCounter) {
        aideInput.addEventListener("input", () => {
            const len = aideInput.value.length;
            aideCounter.textContent = `${len} / 500`;
            aideCounter.className = "char-counter" +
                (len >= 500 ? " at-limit" : len >= 420 ? " near-limit" : "");
        });
    }

    const btnAideSend = $("#btn-aide-send");
    if (btnAideSend) btnAideSend.addEventListener("click", async () => {
        const question = aideInput ? aideInput.value.trim() : "";
        const resultEl = $("#aide-send-result");
        if (!question) {
            if (resultEl) {
                resultEl.textContent = "Veuillez entrer une question avant d'envoyer.";
                resultEl.className = "result-box error";
                show(resultEl);
            }
            return;
        }
        btnAideSend.disabled = true;
        btnAideSend.textContent = "Envoi…";
        try {
            await api("/help-question", { method: "POST", body: JSON.stringify({ question }) });
            if (aideInput) aideInput.value = "";
            if (aideCounter) { aideCounter.textContent = "0 / 500"; aideCounter.className = "aide-char-counter"; }
            if (resultEl) {
                resultEl.textContent = "Merci ! Ta question a bien été envoyée. Nous y répondrons dès que possible.";
                resultEl.className = "result-box";
                show(resultEl);
                setTimeout(() => hide(resultEl), 6000);
            }
        } catch (err) {
            if (resultEl) {
                resultEl.textContent = err.message || "Erreur lors de l'envoi. Réessaie plus tard.";
                resultEl.className = "result-box error";
                show(resultEl);
                setTimeout(() => hide(resultEl), 6000);
            }
        } finally {
            btnAideSend.disabled = false;
            btnAideSend.textContent = "Envoyer la question →";
        }
    });

    // ─── Demo Widget tabs (landing page) ─────────────────────────────────────
    $$(".demo-tab").forEach((tab) => {
        tab.addEventListener("click", () => {
            $$(".demo-tab").forEach((t) => t.classList.remove("active"));
            $$(".demo-panel").forEach((p) => p.classList.remove("active"));
            tab.classList.add("active");
            const panel = $(`#demo-${tab.dataset.demo}`);
            if (panel) panel.classList.add("active");
        });
    });

    // ─── Init ────────────────────────────────────────────────────────────────
    checkSession();
})();
