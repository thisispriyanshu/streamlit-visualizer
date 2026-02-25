"""
Streamlit UI for testing AI Stylist APIs.
Calls backend API and visualizes: Wardrobe Extract, Mix Match, Wardrobe Search, Body Shape, Skin Tone.
Mobile-app style layout for integration preview.
"""
import base64
import io
import json
import os
from typing import Any, Dict, List, Optional

import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DEFAULT_API_BASE = os.getenv("AI_STYLIST_API_URL", "http://localhost:8000").rstrip("/")
STREAMLIT_PAGE_CONFIG = {
    "page_title": "AI Stylist — API Tester",
    "page_icon": "👗",
    "layout": "wide",
    "initial_sidebar_state": "expanded",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def get_api_base() -> str:
    return st.session_state.get("api_base", DEFAULT_API_BASE)


def set_api_base(url: str) -> None:
    st.session_state["api_base"] = url.rstrip("/")


def api_get(path: str, **kwargs) -> requests.Response:
    return requests.get(get_api_base() + path, timeout=60, **kwargs)


def api_post(path: str, **kwargs) -> requests.Response:
    return requests.post(get_api_base() + path, timeout=120, **kwargs)


def render_json(obj: Any) -> None:
    st.json(obj)


def render_image_from_base64(b64: str, caption: Optional[str] = None) -> None:
    """Legacy: prefer render_image() which supports base64 and URL."""
    render_image(b64, caption=caption)


def render_image(value: Any, caption: Optional[str] = None) -> None:
    """
    Display an image from base64 string, data URL (data:image/...;base64,...), or image URL (http/https).
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return
    if not isinstance(value, str):
        return
    value = value.strip()
    try:
        raw: Optional[bytes] = None
        # URL: fetch and display
        if value.startswith("http://") or value.startswith("https://"):
            resp = requests.get(value, timeout=15)
            resp.raise_for_status()
            raw = resp.content
        # Data URL: data:image/...;base64,<b64>
        elif value.startswith("data:"):
            if ";base64," in value:
                b64_part = value.split(";base64,", 1)[1]
                raw = base64.b64decode(b64_part)
            else:
                st.caption("Unsupported data URL format")
                return
        # Plain base64 string
        else:
            raw = base64.b64decode(value)
        if raw:
            st.image(raw, caption=caption or "", use_container_width=True)
    except requests.exceptions.RequestException as e:
        st.caption(f"Image URL error: {e}")
    except Exception as e:
        st.caption(f"Image error: {e}")


def _hex_to_rgb(hex_str: str) -> tuple:
    """Parse #RRGGBB to (r, g, b). Returns (128,128,128) if invalid."""
    h = (hex_str or "").strip().lstrip("#")
    if len(h) != 6:
        return (128, 128, 128)
    try:
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    except ValueError:
        return (128, 128, 128)


def make_color_swatch(hex_str: str, width: int = 80, height: int = 40, border: bool = True) -> Optional[bytes]:
    """Return PNG bytes for a color swatch. border adds a thin gray outline."""
    try:
        from PIL import Image, ImageDraw
        r, g, b = _hex_to_rgb(hex_str)
        img = Image.new("RGB", (width, height), (r, g, b))
        if border:
            draw = ImageDraw.Draw(img)
            draw.rectangle([0, 0, width - 1, height - 1], outline=(180, 180, 180), width=1)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None


def render_color_palette(hex_list: List[str], title: str = "", swatch_height: int = 44, swatch_width: int = 56) -> None:
    """Render a row of color swatches with optional title. Handles string or list of hex."""
    if not hex_list:
        return
    if isinstance(hex_list, str):
        hex_list = [hex_list]
    hex_list = [h for h in hex_list if h and isinstance(h, str)]
    if not hex_list:
        return
    if title:
        st.caption(title)
    cols = st.columns(min(len(hex_list), 8))
    for i, hex_val in enumerate(hex_list[:16]):
        with cols[i % len(cols)]:
            swatch = make_color_swatch(hex_val, width=swatch_width, height=swatch_height)
            if swatch:
                st.image(swatch, caption=hex_val.upper() if hex_val.startswith("#") else f"#{hex_val}".upper(), use_container_width=True)


# ---------------------------------------------------------------------------
# Wardrobe Extract Items
# ---------------------------------------------------------------------------
def tab_wardrobe_extract() -> None:
    st.subheader("Wardrobe Extract Items")
    st.caption("Upload an outfit image to extract individual clothing items. Same flow as mobile: capture → send → show tiles.")

    col1, col2 = st.columns([1, 1])
    with col1:
        image_file = st.file_uploader("Upload outfit image", type=["jpg", "jpeg", "png", "webp"], key="extract_img")
        user_id = st.text_input("User ID (optional)", value="default", key="extract_user_id")
        use_llm_only = st.checkbox("LLM-only extraction", value=True, key="extract_llm_only")
        regenerate_ai = st.checkbox("Regenerate with AI", value=True, key="extract_regen")

    if not image_file:
        st.info("Upload an image to extract wardrobe items.")
        return

    if st.button("Extract items", type="primary", key="btn_extract"):
        with st.spinner("Calling API…"):
            try:
                files = {"image": (image_file.name, image_file.getvalue(), image_file.type or "image/jpeg")}
                data = {
                    "user_id": user_id or None,
                    "highlight_mode": False,
                    "zoom_flag": False,
                    "regenerate_ai_flag": regenerate_ai,
                    "use_llm_detect": True,
                    "use_llm_only_extraction": use_llm_only,
                }
                # Remove None so Form doesn't send "None" string
                data = {k: v for k, v in data.items() if v is not None}
                r = api_post("/api/v1/wardrobe/extract-items", files=files, data=data)
                r.raise_for_status()
                result = r.json()
            except requests.exceptions.RequestException as e:
                st.error(f"API error: {e}")
                if hasattr(e, "response") and e.response is not None:
                    try:
                        st.code(e.response.text[:500])
                    except Exception:
                        pass
                return

        st.success("Extraction complete.")
        meta = result.get("meta", {})
        st.caption(f"Meta: count={meta.get('count', '—')}, min_confidence={meta.get('min_confidence', '—')}")

        # Mobile-style: show extracted items by category as image tiles
        extracted = result.get("extracted_items") or {}
        category_labels = {
            "top_wear": "Tops",
            "bottom_wear": "Bottoms",
            "full_wear": "Full outfit",
            "foot_wear": "Footwear",
            "accessory": "Accessories",
            "bag": "Bags",
        }
        for cat, label in category_labels.items():
            items = extracted.get(cat) or []
            if not items:
                continue
            st.markdown(f"**{label}**")
            cols = st.columns(min(len(items), 4))
            for idx, item in enumerate(items):
                with cols[idx % len(cols)]:
                    img = item.get("image")
                    name = item.get("name") or item.get("description") or "Item"
                    if img:
                        render_image(img, caption=name[:40])
                    else:
                        st.caption(name[:40])
                    if item.get("clothing_type"):
                        st.caption(item["clothing_type"])
                    if item.get("confidence") is not None:
                        st.caption(f"Confidence: {item['confidence']:.2f}")

        with st.expander("Raw response"):
            render_json(result)


# ---------------------------------------------------------------------------
# Mix Match
# ---------------------------------------------------------------------------
def tab_mix_match() -> None:
    st.subheader("Mix Match")
    st.caption("Get outfit suggestions from the user's wardrobe. Same as mobile: user_id + date → outfit cards.")

    user_id = st.text_input("User ID", value="default", key="mix_user_id")
    limit = st.number_input("Max outfits", min_value=1, max_value=50, value=10, key="mix_limit")

    if st.button("Get outfits", type="primary", key="btn_mix"):
        with st.spinner("Calling Mix Match API…"):
            try:
                r = api_post("/api/v1/mix-match/outfits", data={"user_id": user_id}, params={"limit": limit})
                r.raise_for_status()
                result = r.json()
            except requests.exceptions.RequestException as e:
                st.error(f"API error: {e}")
                if hasattr(e, "response") and e.response is not None:
                    try:
                        st.code(e.response.text[:500])
                    except Exception:
                        pass
                return

        st.success("Mix Match complete.")
        outfits = result.get("outfits") or []
        st.caption(f"Found {len(outfits)} outfit(s).")

        for i, o in enumerate(outfits):
            with st.container():
                otype = o.get("type") or o.get("outfit_type") or "—"
                score = o.get("score", 0)
                st.markdown(f"**Outfit {i + 1}** — {otype} (score: {score:.2f})")
                st.caption(o.get("explanation") or "—")

                # Visualize items: use API's items array (with images when available)
                items = o.get("items") or []
                if items:
                    n = len(items)
                    cols = st.columns(min(n, 5))
                    for idx, it in enumerate(items):
                        with cols[idx % len(cols)]:
                            img = it.get("image")
                            if img:
                                render_image(img, caption=it.get("name") or it.get("clothing_type") or "Item")
                            else:
                                name = it.get("name") or it.get("clothing_type") or it.get("id", "Item")
                                st.caption(f"🖼 {name}")
                                if it.get("category"):
                                    st.caption(it["category"])
                else:
                    ids = o.get("selected_item_ids") or o.get("item_ids") or []
                    st.caption(f"Item IDs: {', '.join(ids[:8])}{'…' if len(ids) > 8 else ''}")

        with st.expander("Raw response"):
            render_json(result)


# ---------------------------------------------------------------------------
# Wardrobe Search
# ---------------------------------------------------------------------------
def tab_wardrobe_search() -> None:
    st.subheader("Wardrobe Search")
    st.caption("Search your wardrobe by text (e.g. 'blue casual shirt'). Intent: wardrobe filter or stylist advice.")

    query = st.text_input("Search query", placeholder="e.g. blue casual shirt", key="search_query")
    user_id = st.text_input("User ID", value="default", key="search_user_id")
    context_b64 = st.text_input("Context (context_b64 from previous response)", value="", key="search_context")

    if st.button("Search", type="primary", key="btn_search"):
        if not query or not query.strip():
            st.warning("Enter a search query.")
            return
        with st.spinner("Calling Wardrobe Search API…"):
            try:
                data = {"query": query.strip(), "user_id": user_id or "default"}
                if context_b64 and context_b64.strip():
                    data["context_b64"] = context_b64.strip()
                r = api_post("/api/v1/wardrobe/search", data=data)
                r.raise_for_status()
                result = r.json()
            except requests.exceptions.RequestException as e:
                st.error(f"API error: {e}")
                if hasattr(e, "response") and e.response is not None:
                    try:
                        st.code(e.response.text[:500])
                    except Exception:
                        pass
                return

        st.success("Search complete.")
        intent = result.get("intent", "—")
        st.caption(f"Intent: **{intent}**")

        if intent == "wardrobe_filter":
            # API returns wardrobe_result.extracted_items (category -> list of items with image, name, etc.)
            wardrobe_result = result.get("wardrobe_result") or {}
            items_by_cat = (
                wardrobe_result.get("extracted_items")
                or result.get("items_by_category")
                or result.get("items")
                or {}
            )
            if not isinstance(items_by_cat, dict):
                items_by_cat = {}
            summary = wardrobe_result.get("summary") or result.get("summary") or ""
            if summary:
                st.markdown(summary)
            # Category labels for display
            category_labels = {
                "top_wear": "Tops",
                "bottom_wear": "Bottoms",
                "full_wear": "Full outfit",
                "foot_wear": "Footwear",
                "accessory": "Accessories",
                "bag": "Bags",
            }
            for cat, items in items_by_cat.items():
                if not isinstance(items, list) or not items:
                    continue
                label = category_labels.get(cat, cat.replace("_", " ").title())
                st.markdown(f"**{label}**")
                n = min(len(items), 12)
                cols = st.columns(min(n, 4))
                for idx, it in enumerate(items[:n]):
                    with cols[idx % len(cols)]:
                        img = it.get("image")
                        if img:
                            render_image(img, caption=it.get("name") or it.get("description") or it.get("clothing_type") or "Item")
                        else:
                            st.caption(it.get("name") or it.get("description") or it.get("clothing_type") or "Item")
                if len(items) > n:
                    st.caption(f"… and {len(items) - n} more")
            # Mix match from same response (when include_mix_match was true)
            mix_match = wardrobe_result.get("mix_match") or {}
            mix_outfits = mix_match.get("outfits") or []
            if mix_outfits:
                st.markdown("---")
                st.markdown("**Mix Match from results**")
                for i, o in enumerate(mix_outfits[:5]):
                    with st.container():
                        otype = o.get("type") or o.get("outfit_type") or "—"
                        st.caption(f"Outfit {i + 1} — {otype} (score: {o.get('score', 0):.2f})")
                        st.caption(o.get("explanation") or "—")
                        outfit_items = o.get("items") or []
                        if outfit_items:
                            oc = st.columns(min(len(outfit_items), 5))
                            for j, oit in enumerate(outfit_items):
                                with oc[j % len(oc)]:
                                    oimg = oit.get("image")
                                    if oimg:
                                        render_image(oimg, caption=oit.get("name") or oit.get("clothing_type"))
                                    else:
                                        st.caption(oit.get("name") or oit.get("clothing_type"))
            if result.get("context_b64"):
                st.caption("Copy context_b64 below for follow-up questions:")
                st.code(result["context_b64"][:200] + "…" if len(result.get("context_b64", "")) > 200 else result.get("context_b64", ""))
        else:
            stylist = result.get("stylist_response") or {}
            answer = stylist.get("answer") or result.get("answer") or result.get("message") or ""
            st.markdown(answer)

        with st.expander("Raw response"):
            render_json(result)


# ---------------------------------------------------------------------------
# Body Shape
# ---------------------------------------------------------------------------
def tab_body_shape() -> None:
    st.subheader("Body Shape Detection")
    st.caption("Upload a full-body image and height to analyze body shape. Same as mobile: image + height → shape + result image.")

    col1, col2 = st.columns(2)
    with col1:
        image_file = st.file_uploader("Full-body image", type=["jpg", "jpeg", "png", "webp"], key="body_img")
    with col2:
        height_cm = st.number_input("Height (cm)", min_value=100.0, max_value=250.0, value=170.0, step=0.5, key="body_height")
        debug = st.checkbox("Debug", value=False, key="body_debug")

    if not image_file:
        st.info("Upload a full-body image and set height.")
        return

    if st.button("Analyze body shape", type="primary", key="btn_body"):
        with st.spinner("Calling Body Shape API…"):
            try:
                files = {"image": (image_file.name, image_file.getvalue(), image_file.type or "image/jpeg")}
                data = {"height": height_cm, "debug": debug}
                r = api_post("/api/v1/body-shape/analyze", files=files, data=data)
                r.raise_for_status()
                result = r.json()
            except requests.exceptions.RequestException as e:
                st.error(f"API error: {e}")
                if hasattr(e, "response") and e.response is not None:
                    try:
                        st.code(e.response.text[:500])
                    except Exception:
                        pass
                return

        st.success("Analysis complete.")
        resp = result.get("response") or result
        shape = resp.get("shape") or {}
        confidence = resp.get("confidence")
        result_image_url = resp.get("result_image_url", "")
        msg = resp.get("message", "")

        st.markdown(f"**Shape:** {shape.get('body_shape', shape) if isinstance(shape, dict) else shape}")
        if confidence is not None:
            if isinstance(confidence, dict):
                st.caption(f"Confidence: {json.dumps(confidence)}")
            else:
                st.caption(f"Confidence: {confidence}")
        if msg:
            st.caption(msg)
        if result_image_url:
            # Result image may be relative; show link or fetch if same origin
            base = get_api_base()
            if result_image_url.startswith("/"):
                img_url = base + result_image_url
            else:
                img_url = result_image_url
            try:
                img_r = requests.get(img_url, timeout=10)
                if img_r.status_code == 200:
                    st.image(img_r.content, caption="Result image", use_container_width=True)
                else:
                    st.caption(f"Result image: {img_url}")
            except Exception:
                st.caption(f"Result image URL: {img_url}")

        with st.expander("Raw response"):
            render_json(result)


# ---------------------------------------------------------------------------
# Skin Tone
# ---------------------------------------------------------------------------
def tab_skin_tone() -> None:
    st.subheader("Skin Tone Detection")
    st.caption("Upload a photo with a visible face to detect skin tone and see your palette with colors visualized.")

    image_file = st.file_uploader("Photo with face", type=["jpg", "jpeg", "png", "webp"], key="skin_img")

    if not image_file:
        st.info("Upload a color photo with a visible face.")
        return

    if st.button("Detect skin tone", type="primary", key="btn_skin"):
        with st.spinner("Calling Skin Tone API…"):
            try:
                files = {"image": (image_file.name, image_file.getvalue(), image_file.type or "image/jpeg")}
                r = api_post("/api/v1/skin-tone/detect", files=files)
                r.raise_for_status()
                result = r.json()
            except requests.exceptions.RequestException as e:
                st.error(f"API error: {e}")
                if hasattr(e, "response") and e.response is not None:
                    try:
                        st.code(e.response.text[:500])
                    except Exception:
                        pass
                return

        st.success("Detection complete.")
        # Faces can be under input.faces (LLM response) or top-level faces
        faces = result.get("input", {}).get("faces") or result.get("faces") or []
        stylist_recs = result.get("stylist_recs") or {}

        if not faces:
            st.caption("No faces in response. Raw keys: " + ", ".join(result.keys()))

        # Layout: image on left, palette on right
        col_img, col_palette = st.columns([1, 1])
        with col_img:
            image_file.seek(0)
            st.image(image_file, caption="Your photo", use_container_width=True)

        with col_palette:
            for i, face in enumerate(faces):
                tone = face.get("skin_tone") or face.get("skin_tone_hex") or ""
                tone_label = face.get("tone_label", "")
                undertone = face.get("undertone", "")
                dominant_colors = face.get("dominant_colors") or []

                st.markdown(f"**Face {i + 1}** — Skin tone")
                # Primary skin tone: large swatch + hex
                if tone:
                    swatch_big = make_color_swatch(tone, width=140, height=80)
                    if swatch_big:
                        st.image(swatch_big, caption=f"**{tone.upper() if tone.startswith('#') else '#' + tone.upper()}**", use_container_width=False)
                    st.markdown(f"**{tone.upper() if tone.startswith('#') else '#' + tone.upper()}**")
                    if tone_label:
                        st.caption(f"Tone: {tone_label}")
                    if undertone:
                        st.caption(f"Undertone: {undertone}")

                # Dominant colors from engine (with percent if available)
                if dominant_colors:
                    st.markdown("**Dominant colors**")
                    hex_list = []
                    for dc in dominant_colors[:8]:
                        c = dc.get("color") or dc.get("hex") or ""
                        if c:
                            hex_list.append(c)
                    if hex_list:
                        render_color_palette(hex_list, swatch_height=48, swatch_width=64)
                    # Optional: show percents in captions
                    cols_d = st.columns(min(len(dominant_colors), 6))
                    for j, dc in enumerate(dominant_colors[:6]):
                        with cols_d[j]:
                            c = dc.get("color") or dc.get("hex")
                            pct = dc.get("percent")
                            if c:
                                s = make_color_swatch(c, width=56, height=32)
                                if s:
                                    st.image(s, use_container_width=True)
                                label = c.upper() if c.startswith("#") else f"#{c}".upper()
                                if pct is not None:
                                    label += f" ({float(pct):.0f}%)"
                                st.caption(label)

        # Stylist recommendations: swatches and recommended palettes
        if stylist_recs:
            st.markdown("---")
            st.markdown("### Your color palette & recommendations")

            profile = stylist_recs.get("profile") or {}
            if profile.get("summary_line"):
                st.info(profile["summary_line"])
            ui = stylist_recs.get("ui") or {}
            if ui.get("title"):
                st.markdown(f"**{ui['title']}**")
            if ui.get("subtitle"):
                st.caption(ui["subtitle"])

            # Main swatches block: skin_tone, dominant, metal, clothing, etc.
            swatches = stylist_recs.get("swatches") or {}
            if swatches:
                st.markdown("**Detected & recommended swatches**")
                for key, val in swatches.items():
                    if not val:
                        continue
                    label = key.replace("_", " ").title()
                    if isinstance(val, list):
                        render_color_palette(val, title=label, swatch_height=52, swatch_width=60)
                    else:
                        render_color_palette([val], title=label, swatch_height=52, swatch_width=60)

            # Recommendations with hex arrays (lipstick, blush, clothing, etc.)
            recs = stylist_recs.get("recommendations") or {}
            for rec_key, rec_val in recs.items():
                if not isinstance(rec_val, dict):
                    continue
                label = rec_val.get("label", rec_key.replace("_", " ").title())
                st.markdown(f"**{label}**")
                hex_arr = rec_val.get("hex")
                if isinstance(hex_arr, list) and hex_arr:
                    render_color_palette(hex_arr, swatch_height=44, swatch_width=52)
                elif isinstance(hex_arr, dict):
                    # e.g. clothing_palette.hex = { "camel": "#...", ... }
                    render_color_palette(list(hex_arr.values()), title="", swatch_height=44, swatch_width=52)
                top_picks = rec_val.get("top_picks") or rec_val.get("alternates")
                if top_picks and isinstance(top_picks, list):
                    st.caption(", ".join(str(p) for p in top_picks[:8]))

        with st.expander("Raw response"):
            render_json(result)


# ---------------------------------------------------------------------------
# Layout: sidebar + tabs + mobile preview note
# ---------------------------------------------------------------------------
def main() -> None:
    st.set_page_config(**STREAMLIT_PAGE_CONFIG)

    with st.sidebar:
        st.header("API Config")
        api_base = st.text_input("API base URL", value=get_api_base(), key="api_base_input")
        if api_base and api_base.strip():
            set_api_base(api_base.strip())
        else:
            set_api_base(DEFAULT_API_BASE)
        st.caption("e.g. http://localhost:8000")
        st.divider()
        st.caption("This UI calls your backend and shows results as they would appear in a mobile app.")

    st.title("AI Stylist — API Tester")
    st.caption("Wardrobe Extract • Mix Match • Wardrobe Search • Body Shape • Skin Tone")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Wardrobe Extract",
        "Mix Match",
        "Wardrobe Search",
        "Body Shape",
        "Skin Tone",
    ])

    with tab1:
        tab_wardrobe_extract()
    with tab2:
        tab_mix_match()
    with tab3:
        tab_wardrobe_search()
    with tab4:
        tab_body_shape()
    with tab5:
        tab_skin_tone()

    # Mobile preview hint + optional narrow layout
    st.divider()
    mobile_preview = st.checkbox("Mobile preview (narrow layout)", value=False, key="mobile_preview")
    if mobile_preview:
        st.markdown(
            "<style>div.block-container { max-width: 420px; margin-left: auto; margin-right: auto; }</style>",
            unsafe_allow_html=True,
        )
    st.caption("Mobile preview: Use a narrow browser window or DevTools device mode to simulate app layout.")


if __name__ == "__main__":
    main()
