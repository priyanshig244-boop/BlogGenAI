import streamlit as st
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from io import BytesIO
import html

# Optional export libraries:
# Install with: pip install -r requirements.txt
try:
    from docx import Document
except ImportError:
    Document = None

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.styles import ParagraphStyle
except ImportError:
    SimpleDocTemplate = None


# ==================================================
# 1. PAGE CONFIGURATION
# ==================================================
st.set_page_config(page_title="BlogGen AI", page_icon="✍️", layout="wide")
DB_PATH = Path(__file__).with_name("blogs.db")


# ==================================================
# 2. DATABASE: HISTORY AND SAVED BLOGS
# ==================================================
def get_connection():
    return sqlite3.connect(DB_PATH)


def setup_database():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                blog TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS saved_blogs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                topic TEXT NOT NULL,
                blog TEXT NOT NULL,
                created_at TEXT NOT NULL,
                is_favorite INTEGER NOT NULL DEFAULT 0
            )
        """)

        # Safely add the favorite column to older databases.
        columns = [
            row[1] for row in conn.execute("PRAGMA table_info(saved_blogs)").fetchall()
        ]
        if "is_favorite" not in columns:
            conn.execute(
                "ALTER TABLE saved_blogs ADD COLUMN is_favorite INTEGER NOT NULL DEFAULT 0"
            )


def add_to_history(topic, blog):
    created_at = datetime.now().strftime("%d %b %Y, %I:%M %p")
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO history (topic, blog, created_at) VALUES (?, ?, ?)",
            (topic, blog, created_at)
        )


def get_history():
    with get_connection() as conn:
        return conn.execute(
            "SELECT id, topic, blog, created_at FROM history ORDER BY id DESC"
        ).fetchall()


def delete_history(blog_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM history WHERE id = ?", (blog_id,))


def clear_history():
    with get_connection() as conn:
        conn.execute("DELETE FROM history")


def save_blog(title, topic, blog):
    created_at = datetime.now().strftime("%d %b %Y, %I:%M %p")
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO saved_blogs (title, topic, blog, created_at)
               VALUES (?, ?, ?, ?)""",
            (title, topic, blog, created_at)
        )


def get_saved_blogs():
    with get_connection() as conn:
        return conn.execute(
            """SELECT id, title, topic, blog, created_at, is_favorite
               FROM saved_blogs ORDER BY is_favorite DESC, id DESC"""
        ).fetchall()


def delete_saved(blog_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM saved_blogs WHERE id = ?", (blog_id,))


def toggle_favorite(blog_id, current_value):
    with get_connection() as conn:
        conn.execute(
            "UPDATE saved_blogs SET is_favorite = ? WHERE id = ?",
            (0 if current_value else 1, blog_id)
        )


setup_database()


# ==================================================
# 3. SESSION STATE
# ==================================================
defaults = {
    "blog": "",
    "topic": "",
    "seo": "",
    "selected_history": None,
    "selected_saved": None,
    "theme": "Light",
    "editor_version": 0,
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ==================================================
# 4. LIGHT/DARK THEME AND STYLING
# ==================================================
st.sidebar.title("⚙️ Settings")
theme = st.sidebar.radio(
    "Appearance",
    ["Light", "Dark"],
    index=0 if st.session_state.theme == "Light" else 1
)
st.session_state.theme = theme

if theme == "Dark":
    page_bg = "linear-gradient(135deg, #15152B, #20233D, #35213D)"
    card_bg = "rgba(37, 39, 65, 0.96)"
    text_color = "#F5F3FF"
    border_color = "#494566"
    input_bg = "#292B46"
else:
    page_bg = "linear-gradient(135deg, #F0E7FF, #E8F0FF, #FFE8F5)"
    card_bg = "rgba(255, 255, 255, 0.95)"
    text_color = "#252344"
    border_color = "#E2D9F5"
    input_bg = "#FFFFFF"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Poppins:wght@500;600;700;800&display=swap');
.stApp, [data-testid="stAppViewContainer"] {{
    background: {page_bg};
    color: {text_color};
    font-family: 'Inter', sans-serif;
}}
[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ max-width: 1050px; padding-top: 2rem; padding-bottom: 3rem; }}
h1, h2, h3 {{ font-family: 'Poppins', sans-serif !important; color: {text_color} !important; }}
p, label, .stMarkdown, .stCaption {{ color: {text_color}; }}
.stButton > button, .stDownloadButton > button {{
    border: none; border-radius: 14px; padding: 0.65rem 1rem;
    font-weight: 700; color: white;
    background: linear-gradient(100deg, #805AD5, #4776E6, #D65DB1);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}}
.stButton > button:hover, .stDownloadButton > button:hover {{
    transform: translateY(-2px); box-shadow: 0 7px 20px rgba(100, 70, 190, 0.25);
}}
div[data-testid="stTextArea"] textarea, div[data-testid="stTextInput"] input {{
    background: {input_bg}; color: {text_color}; border-radius: 12px;
}}
div[data-baseweb="select"] > div {{ background: {input_bg}; color: {text_color}; border-radius: 12px; }}
.hero {{
    background: linear-gradient(110deg, #805AD5, #4776E6, #D65DB1);
    padding: 2rem; border-radius: 24px; color: white; margin-bottom: 1.4rem;
    box-shadow: 0 12px 30px rgba(85, 70, 180, 0.20);
}}
.hero h1, .hero p {{ color: white !important; }}
@media (max-width: 640px) {{
    .block-container {{ padding: 1rem 0.8rem 2rem; }}
    .hero {{ padding: 1.3rem; }}
}}
</style>
""", unsafe_allow_html=True)


# ==================================================
# 5. PYTHON-ONLY BLOG TEMPLATES
# ==================================================
def generate_blog(topic, tone, length, audience, language):
    """Generate a structured article from reusable Python templates."""
    topic = topic.strip()
    title = topic.title()
    words = re.findall(r"[a-zA-Z0-9]+", topic.lower())
    keywords = list(dict.fromkeys(word for word in words if len(word) > 2))
    keyword_text = ", ".join(keywords[:8]) or topic

    section_counts = {"Short": 3, "Medium": 5, "Long": 8}
    section_count = section_counts.get(length, 5)

    introductions = {
        "Professional": (
            f"{topic} is an important subject that deserves careful consideration. "
            "Understanding its principles, practical relevance, potential benefits, "
            "and limitations can help readers develop a more informed perspective. "
            "This article examines the topic in a structured and accessible way."
        ),
        "Conversational": (
            f"Have you ever wanted to understand {topic} better? Let's explore the "
            "main ideas, look at why they matter, and discover practical ways to "
            "learn more. We will break the subject into smaller, easier-to-understand parts."
        ),
        "Educational": (
            f"This guide introduces {topic} through a step-by-step explanation. "
            "It covers the fundamentals, important features, possible benefits, "
            "practical applications, and common challenges to help readers build a foundation."
        ),
        "Creative": (
            f"Curiosity often begins with one simple question: what makes {topic} worth "
            "exploring? By examining its main ideas, possibilities, and connections to "
            "everyday situations, we can discover new ways to understand the subject."
        )
    }

    sections = [
        (f"Understanding {title}",
         f"The first step is to understand what {topic} means, how it is generally "
         f"described, and why it matters to {audience.lower()}. Start with the fundamental "
         "concepts and identify the most important terms. Instead of trying to memorize "
         "everything at once, divide the subject into smaller parts and study them individually. "
         "Try explaining the main idea in your own words. Connecting new information with what "
         "you already know makes it easier to understand and remember."),
        ("Why This Topic Matters",
         f"The importance of {topic} depends on the situation in which it is studied or applied. "
         "Learning about it can increase awareness, introduce different perspectives, and help "
         "people evaluate available choices. Students may use relevant knowledge in assignments "
         "and projects, while other readers may connect it with their interests or professional "
         "goals. Understanding the context is essential because a concept that is useful in one "
         "situation may not be equally useful in every other situation."),
        ("Key Benefits and Opportunities",
         f"Exploring {topic} can offer several potential benefits. It can expand knowledge, "
         "strengthen critical thinking, and encourage people to investigate questions more deeply. "
         "Studying different examples also helps readers compare ideas and recognize patterns. "
         "Another opportunity is the chance to apply learning through exercises, discussions, "
         "or small projects. These benefits depend on the quality of the information and the "
         "effort invested in learning. A balanced approach considers both opportunities and limits."),
        ("Practical Applications and Examples",
         f"One effective way to understand {topic} is to connect it with practical situations. "
         "Begin with a familiar example and identify which concepts are relevant. Then consider "
         "how those concepts might explain the situation or help address a problem. Students can "
         "use case studies, classroom activities, and small projects. Independent learners can "
         "explore examples from books and educational resources. Record what you learn from each "
         "example and compare it with the original concept. This process helps turn theoretical "
         "knowledge into a more useful understanding."),
        ("Common Challenges and Limitations",
         f"Learning about {topic} may involve unfamiliar terminology, conflicting explanations, "
         "or difficulty finding suitable examples. Beginners sometimes accept the first explanation "
         "they encounter without checking its reliability. A better approach is to compare credible "
         "sources, identify the context behind important claims, and distinguish facts from opinions. "
         "It is also important to recognize that no single explanation necessarily covers every "
         "situation. Understanding limitations leads to a more thoughtful and balanced perspective."),
        ("A Step-by-Step Guide for Beginners",
         f"Start learning {topic} by setting one clear and achievable goal. Find a beginner-friendly "
         "resource and note the main concepts. Divide the subject into manageable sections so each "
         "learning session has a specific purpose. After reading, summarize the information without "
         "looking at the original material. Next, work through a simple exercise or practical example. "
         "Review your notes regularly and maintain a list of questions that need further research. "
         "Gradually increase the difficulty as your understanding grows."),
        ("Useful Tips and Best Practices",
         f"To improve your understanding of {topic}, make learning active rather than simply rereading "
         "the same material. Explain concepts in your own words, create concise notes, and test yourself "
         "with examples. If a topic seems confusing, look for a different explanation and compare the "
         "evidence. Set realistic milestones and revisit difficult concepts after a short interval. "
         "Consistency is more useful than trying to learn everything in one session. Reviewing your "
         "progress helps identify which areas need more attention."),
        ("Future Learning and Further Exploration",
         f"Once you understand the fundamentals of {topic}, you can explore related concepts and more "
         "detailed examples. Ask which questions remain unanswered and which assumptions need checking. "
         "Seek reliable books, educational materials, and examples relevant to your interests. As new "
         "information becomes available, revisit older notes and check whether the information remains "
         "accurate. Continued learning allows you to move beyond an introductory overview and develop "
         "a deeper understanding.")
    ]

    conclusion = (
        f"Understanding {topic} begins with learning its core ideas and continues through practice, "
        "research, and thoughtful evaluation. By considering its applications, potential benefits, "
        "and limitations, readers can develop a more balanced perspective. Start with manageable "
        "learning goals, use reliable information, and build on your knowledge gradually. A clear "
        "foundation makes it easier to explore the subject in greater depth."
    )

    if language == "Hindi":
        hindi_sections = [
            ("विषय को समझना", f"{topic} को समझने के लिए सबसे पहले इसकी मूल अवधारणा, उद्देश्य और प्रमुख विशेषताओं को जानना उपयोगी है। विषय को छोटे भागों में बांटकर पढ़ने से जानकारी अधिक स्पष्ट होती है।"),
            ("इसका महत्व", f"{topic} का महत्व इस बात पर निर्भर करता है कि इसे किस परिस्थिति में समझा या उपयोग किया जाता है। इसका अध्ययन नई जानकारी प्राप्त करने और अलग-अलग दृष्टिकोण समझने में मदद कर सकता है।"),
            ("प्रमुख लाभ", f"{topic} के बारे में सीखने से जागरूकता, समझ और समस्या को अलग-अलग दृष्टिकोण से देखने की क्षमता बढ़ सकती है। इसके लाभ सही जानकारी और नियमित अभ्यास पर निर्भर करते हैं।"),
            ("व्यावहारिक उपयोग", f"{topic} को उदाहरणों, छोटे प्रोजेक्ट, समूह चर्चा और स्वतंत्र अध्ययन के माध्यम से समझा जा सकता है। व्यावहारिक अभ्यास से सैद्धांतिक जानकारी को वास्तविक परिस्थितियों से जोड़ना आसान होता है।"),
            ("चुनौतियां और सीमाएं", f"{topic} सीखते समय कठिन शब्दों, अधूरी जानकारी या अलग-अलग विचारों का सामना करना पड़ सकता है। इसलिए विश्वसनीय स्रोतों से जानकारी की पुष्टि करना और तथ्यों को ध्यान से समझना महत्वपूर्ण है।"),
            ("शुरुआत कैसे करें", f"{topic} की मूल बातें सीखें, महत्वपूर्ण बिंदुओं के नोट्स बनाएं और छोटे उदाहरणों से अभ्यास करें। नियमित रूप से दोहराने और सवाल पूछने से समझ विकसित करने में मदद मिल सकती है।"),
            ("उपयोगी सुझाव", "सीखने के लिए छोटे लक्ष्य बनाएं, जानकारी की तुलना करें और कठिन अवधारणाओं को दोबारा पढ़ें। अपनी भाषा में समझाना भी ज्ञान जांचने का उपयोगी तरीका है।"),
            ("आगे सीखने के अवसर", f"{topic} की बुनियादी जानकारी के बाद संबंधित विषयों, विस्तृत उदाहरणों और विश्वसनीय शैक्षणिक संसाधनों का अध्ययन किया जा सकता है।")
        ]
        blog = (
            f"# {title}\n\n**लक्षित पाठक:** {audience}\n\n"
            f"**लेखन शैली:** {tone}\n\n**लेख की लंबाई:** {length}\n\n"
            f"## परिचय\n\n{topic} एक ऐसा विषय है जिसे समझने के लिए इसके मूल विचारों, "
            "महत्व और व्यावहारिक उपयोग पर ध्यान देना उपयोगी है। इस लेख में हम इसके प्रमुख "
            "पहलुओं, संभावित लाभों, चुनौतियों और सीखने के तरीकों को सरल भाषा में समझेंगे।\n\n"
        )
        for heading, paragraph in hindi_sections[:section_count]:
            blog += f"## {heading}\n\n{paragraph}\n\n"
        blog += (
            f"## निष्कर्ष\n\n{topic} को बेहतर तरीके से समझने के लिए सही जानकारी, नियमित "
            "अभ्यास और सोच-समझकर अध्ययन करना आवश्यक है। इसके लाभों के साथ-साथ इसकी सीमाओं "
            "को समझना भी जरूरी है। छोटे लक्ष्य बनाकर और विश्वसनीय स्रोतों का उपयोग करके "
            "विषय की समझ को धीरे-धीरे बेहतर बनाया जा सकता है।"
        )
        return blog

    blog = (
        f"# {title}\n\n**Target audience:** {audience}\n\n"
        f"**Writing tone:** {tone}\n\n**Blog length:** {length}\n\n"
        f"## Introduction\n\n{introductions[tone]}\n\n"
        "## Key Takeaways\n\n"
        f"- Understand the fundamentals of {topic}.\n"
        "- Explore practical examples and possible applications.\n"
        "- Consider both opportunities and limitations.\n"
        "- Use reliable information and continue learning.\n\n"
    )
    for heading, paragraph in sections[:section_count]:
        blog += f"## {heading}\n\n{paragraph}\n\n"
    blog += (
        f"## Conclusion\n\n{conclusion}\n\n"
        "## SEO Suggestions\n\n"
        f"**Main topic:** {topic}\n\n"
        f"**Related keywords:** {keyword_text}\n\n"
        "*Editorial note: This article uses Python templates. Verify topic-specific facts "
        "and add reliable sources before publishing.*"
    )
    return blog


# ==================================================
# 6. UTILITIES: WORD COUNT, EXPORT, SHARE
# ==================================================
def word_count(text):
    return len(re.findall(r"\b[\w'-]+\b", text, flags=re.UNICODE))


def reading_time(text):
    # Approximation: 200 words per minute.
    words = word_count(text)
    return max(1, (words + 199) // 200)


def markdown_to_plain_text(markdown_text):
    """Simple Markdown cleanup for text exports."""
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", markdown_text, flags=re.MULTILINE)
    text = re.sub(r"(\*\*|__)(.*?)\1", r"\2", text)
    text = re.sub(r"(\*|_)(.*?)\1", r"\2", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    return text


def make_docx(markdown_text):
    if Document is None:
        return None

    document = Document()
    for line in markdown_text.splitlines():
        line = line.rstrip()
        if not line:
            continue
        if line.startswith("# "):
            document.add_heading(line[2:], level=1)
        elif line.startswith("## "):
            document.add_heading(line[3:], level=2)
        elif line.startswith("### "):
            document.add_heading(line[4:], level=3)
        elif line.startswith("- "):
            document.add_paragraph(line[2:], style="List Bullet")
        else:
            # Strip basic Markdown emphasis for a clean Word document.
            clean = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
            clean = re.sub(r"\*(.*?)\*", r"\1", clean)
            document.add_paragraph(clean)

    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def make_pdf(markdown_text):
    if SimpleDocTemplate is None:
        return None

    buffer = BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    for line in markdown_text.splitlines():
        line = line.strip()
        if not line:
            story.append(Spacer(1, 8))
            continue

        safe_line = html.escape(markdown_to_plain_text(line))
        if line.startswith("# "):
            story.append(Paragraph(safe_line[2:] if safe_line.startswith("# ") else safe_line,
                                   styles["Title"]))
            story.append(Spacer(1, 10))
        elif line.startswith("## "):
            story.append(Paragraph(html.escape(line[3:]), styles["Heading2"]))
        elif line.startswith("### "):
            story.append(Paragraph(html.escape(line[4:]), styles["Heading3"]))
        else:
            story.append(Paragraph(safe_line, styles["BodyText"]))
            story.append(Spacer(1, 5))

    pdf.build(story)
    return buffer.getvalue()


def show_blog_tools(blog_text, file_prefix, key_prefix):
    """Render copy, export, and social sharing tools for a blog."""
    plain_text = markdown_to_plain_text(blog_text)
    safe_text = html.escape(plain_text)

    st.markdown(
        f"**Words:** {word_count(blog_text)}  ·  "
        f"**Estimated reading time:** {reading_time(blog_text)} min"
    )

    # Clipboard API runs in the user's browser.
    copy_component = f"""
    <div style="margin: 4px 0 12px 0;">
      <button id="copy-{key_prefix}"
        style="background:linear-gradient(100deg,#805AD5,#4776E6,#D65DB1);
        border:0;border-radius:12px;padding:10px 18px;color:white;
        font-weight:700;cursor:pointer;">
        📋 Copy Blog
      </button>
      <span id="copy-status-{key_prefix}" style="margin-left:10px;"></span>
    </div>
    <textarea id="copy-source-{key_prefix}" style="position:absolute;left:-9999px;">{safe_text}</textarea>
    <script>
    const btn = document.getElementById("copy-{key_prefix}");
    btn.addEventListener("click", async () => {{
      const text = document.getElementById("copy-source-{key_prefix}").value;
      try {{
        await navigator.clipboard.writeText(text);
        document.getElementById("copy-status-{key_prefix}").textContent = "Copied!";
      }} catch (e) {{
        const source = document.getElementById("copy-source-{key_prefix}");
        source.style.position = "static";
        source.select();
        document.execCommand("copy");
        source.style.position = "absolute";
        source.style.left = "-9999px";
        document.getElementById("copy-status-{key_prefix}").textContent = "Copy attempted.";
      }}
    }});
    </script>
    """
    # Use the browser clipboard component; fallback is the visible code block below.
    st.components.v1.html(copy_component, height=55)

    col_txt, col_docx, col_pdf = st.columns(3)

    with col_txt:
        st.download_button(
            "⬇️ Text (.txt)",
            data=plain_text,
            file_name=f"{file_prefix}.txt",
            mime="text/plain",
            key=f"{key_prefix}_txt",
            use_container_width=True
        )

    with col_docx:
        docx_bytes = make_docx(blog_text)
        if docx_bytes is not None:
            st.download_button(
                "📄 Word (.docx)",
                data=docx_bytes,
                file_name=f"{file_prefix}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key=f"{key_prefix}_docx",
                use_container_width=True
            )
        else:
            st.caption("Install python-docx for Word export.")

    with col_pdf:
        pdf_bytes = make_pdf(blog_text)
        if pdf_bytes is not None:
            st.download_button(
                "📕 PDF",
                data=pdf_bytes,
                file_name=f"{file_prefix}.pdf",
                mime="application/pdf",
                key=f"{key_prefix}_pdf",
                use_container_width=True
            )
        else:
            st.caption("Install reportlab for PDF export.")

    st.markdown("**Share this blog**")
    # Social sharing links open a new post/message with text prefilled.
    share_text = plain_text[:1800]
    encoded_text = quote(share_text)
    encoded_url = quote("https://example.com", safe="")
    wa_url = f"https://wa.me/?text={encoded_text}%0A%0A{encoded_url}"
    linkedin_url = f"https://www.linkedin.com/sharing/share-offsite/?url={encoded_url}"
    x_url = f"https://twitter.com/intent/tweet?text={quote(plain_text[:240])}&url={encoded_url}"

    share1, share2, share3 = st.columns(3)
    with share1:
        st.link_button("WhatsApp", wa_url, use_container_width=True)
    with share2:
        st.link_button("LinkedIn", linkedin_url, use_container_width=True)
    with share3:
        st.link_button("X", x_url, use_container_width=True)

    st.caption(
        "Sharing uses a placeholder website URL until you deploy your app. "
        "Replace https://example.com in the code with your published blog or website URL."
    )


# ==================================================
# 7. HEADER
# ==================================================
st.markdown("""
<div class="hero">
    <h1>✍️ BlogGen AI</h1>
    <p>Your personal space to create, edit, and organize blog posts.</p>
</div>
""", unsafe_allow_html=True)
st.caption("Create, customize, edit and organize detailed blog posts.")


# ==================================================
# 8. TABS
# ==================================================
tab_create, tab_history, tab_saved, tab_about = st.tabs([
    "✨ Create Blog", "🕘 History", "💜 Saved Blogs", "ℹ️ About"
])


# ==================================================
# 9. CREATE BLOG
# ==================================================
with tab_create:
    st.subheader("Create a new blog")
    topic = st.text_input(
        "Enter your blog topic",
        value=st.session_state.topic,
        placeholder="Example: Benefits of Artificial Intelligence",
        key="topic_input"
    )

    col1, col2 = st.columns(2)
    with col1:
        tone = st.selectbox(
            "Writing tone",
            ["Professional", "Conversational", "Educational", "Creative"]
        )
        length = st.selectbox(
            "Blog length", ["Short", "Medium", "Long"], index=2
        )
    with col2:
        audience = st.selectbox(
            "Target audience",
            ["Students", "Beginners", "Professionals", "General Readers"]
        )
        language = st.selectbox("Language", ["English", "Hindi"])

    if st.button("✨ Generate Blog", use_container_width=True):
        if not topic.strip():
            st.warning("Please enter a topic first.")
        else:
            blog = generate_blog(topic, tone, length, audience, language)
            st.session_state.blog = blog
            st.session_state.topic = topic
            keywords = list(dict.fromkeys(
                re.findall(r"\b[a-zA-Z0-9]+\b", topic.lower())
            ))
            st.session_state.seo = ", ".join(keywords[:8])
            add_to_history(topic, blog)
            st.success("Your blog has been generated!")

    if st.session_state.blog:
        st.divider()
        st.subheader("📝 Your Blog")

        # The current edited content is the source for save, copy and downloads.
        editor_key = f"blog_editor_{st.session_state.editor_version}"
        edited_blog = st.text_area(
            "Edit your blog before saving or sharing",
            value=st.session_state.blog,
            height=480,
            key=editor_key
        )
        st.session_state.blog = edited_blog

        st.subheader("🔎 SEO Suggestions")
        st.write("**Suggested keywords:**", st.session_state.seo)
        st.write("**Suggested title:**", st.session_state.topic.title())

        show_blog_tools(
            edited_blog,
            "my_blog",
            f"current_{st.session_state.editor_version}"
        )

        st.divider()
        save_col, reset_col = st.columns(2)
        with save_col:
            if st.button("💜 Save Edited Blog", use_container_width=True):
                save_blog(
                    st.session_state.topic.title(),
                    st.session_state.topic,
                    edited_blog
                )
                st.success("Edited blog saved!")
        with reset_col:
            if st.button("↩️ Restore Generated Version", use_container_width=True):
                st.session_state.blog = generate_blog(
                    st.session_state.topic, tone, length, audience, language
                )
                st.session_state.editor_version += 1
                st.rerun()

        st.subheader("👀 Preview")
        st.markdown(edited_blog)


# ==================================================
# 10. HISTORY
# ==================================================
with tab_history:
    st.subheader("🕘 Blog History")
    st.write("Every generated blog appears here automatically.")

    history_search = st.text_input(
        "Search history",
        placeholder="Search by topic or blog content...",
        key="history_search"
    ).strip().lower()
    history_sort = st.selectbox(
        "Sort history by date",
        ["Newest first", "Oldest first"],
        key="history_sort"
    )

    history = get_history()
    if history_search:
        history = [
            item for item in history
            if history_search in item[1].lower()
            or history_search in item[2].lower()
        ]
    if history_sort == "Oldest first":
        history = list(reversed(history))

    if not history:
        st.info("No blogs generated yet. Create your first blog!")
    else:
        if st.button("🗑️ Clear All History"):
            clear_history()
            st.session_state.selected_history = None
            st.rerun()

        for blog_id, old_topic, old_blog, created_at in history:
            preview = re.sub(r"[#*`_]", "", old_blog).strip()
            preview = preview[:180] + ("..." if len(preview) > 180 else "")
            with st.expander(f"📄 {old_topic} · {created_at}"):
                st.caption(f"Created: {created_at}")
                st.write(preview)
                h1, h2 = st.columns(2)
                with h1:
                    if st.button("Open Blog", key=f"open_history_{blog_id}"):
                        st.session_state.selected_history = blog_id
                with h2:
                    if st.button("Delete", key=f"delete_history_{blog_id}"):
                        delete_history(blog_id)
                        if st.session_state.selected_history == blog_id:
                            st.session_state.selected_history = None
                        st.rerun()

        selected_id = st.session_state.selected_history
        if selected_id is not None:
            selected = next((item for item in get_history() if item[0] == selected_id), None)
            if selected:
                st.divider()
                st.subheader(f"📖 {selected[1]}")
                st.caption(f"Created: {selected[3]}")
                st.markdown(selected[2])
                show_blog_tools(selected[2], "history_blog", f"history_{selected_id}")


# ==================================================
# 11. SAVED BLOGS
# ==================================================
with tab_saved:
    st.subheader("💜 Saved Blogs")
    search_term = st.text_input(
        "Search saved blogs",
        placeholder="Search by title, topic, or keyword...",
        key="saved_search"
    ).strip().lower()
    saved_sort = st.selectbox(
        "Sort saved blogs by date",
        ["Newest first", "Oldest first", "Favorites first"],
        key="saved_sort"
    )

    saved = get_saved_blogs()
    matching = [
        item for item in saved
        if search_term in item[1].lower()
        or search_term in item[2].lower()
        or search_term in item[3].lower()
    ]

    if saved_sort == "Oldest first":
        matching = sorted(matching, key=lambda item: item[0])
    elif saved_sort == "Favorites first":
        matching = sorted(matching, key=lambda item: (item[5], item[0]), reverse=True)
    else:
        matching = sorted(matching, key=lambda item: item[0], reverse=True)

    if not saved:
        st.info("You haven't saved any blogs yet.")
    elif not matching:
        st.warning("No saved blogs match your search.")
    else:
        for saved_id, title, saved_topic, saved_blog, saved_date, is_favorite in matching:
            pin_mark = "📌 " if is_favorite else ""
            with st.expander(f"{pin_mark}💜 {title} · {saved_date}"):
                st.caption(f"Topic: {saved_topic}")
                st.write(saved_blog[:180] + ("..." if len(saved_blog) > 180 else ""))
                s1, s2, s3 = st.columns(3)
                with s1:
                    if st.button("Open Blog", key=f"open_saved_{saved_id}"):
                        st.session_state.selected_saved = saved_id
                with s2:
                    favorite_label = "Unpin" if is_favorite else "📌 Pin / Favorite"
                    if st.button(favorite_label, key=f"favorite_saved_{saved_id}"):
                        toggle_favorite(saved_id, is_favorite)
                        st.rerun()
                with s3:
                    if st.button("Delete", key=f"delete_saved_{saved_id}"):
                        delete_saved(saved_id)
                        if st.session_state.selected_saved == saved_id:
                            st.session_state.selected_saved = None
                        st.rerun()

        selected_saved_id = st.session_state.selected_saved
        if selected_saved_id is not None:
            selected_saved = next(
                (item for item in get_saved_blogs() if item[0] == selected_saved_id),
                None
            )
            if selected_saved:
                st.divider()
                st.subheader(f"📖 {selected_saved[1]}")
                st.caption(f"Saved: {selected_saved[4]}")
                show_blog_tools(
                    selected_saved[3],
                    "saved_blog",
                    f"saved_{selected_saved_id}"
                )


# ==================================================
# 12. ABOUT AND FOOTER
# ==================================================
with tab_about:
    st.subheader("About BlogGen AI")
    st.write("""
    BlogGen AI helps you create, edit, export, and organize blog posts.

    **Features**
    - Python template-based generation
    - Multiple tones, lengths, audiences, and languages
    - Searchable history with newest-first or oldest-first sorting
    - Searchable saved blogs with date sorting
    - Favorite/pin saved blogs and show favorites first
    - SEO keyword suggestions
    - Edit before saving, copying, sharing, or downloading
    - PDF, Word, and text file exports
    - Word count and estimated reading time
    - WhatsApp, LinkedIn, and X sharing shortcuts
    - Purple gradient design with light and dark themes
    """)
    st.caption("Your history and saved blogs are stored locally in blogs.db.")

st.divider()
st.caption("BlogGen AI | Built with Python and Streamlit")
