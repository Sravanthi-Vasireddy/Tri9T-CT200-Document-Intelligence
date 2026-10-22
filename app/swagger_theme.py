"""
Custom Swagger UI Styling for Tri9T-CT200-Document-Intelligence.
Applies an enterprise Navy/Indigo theme matching the React frontend.
"""

SWAGGER_CUSTOM_CSS = """
/* ========================================================
   Tri9T-CT200 Document Intelligence — Custom Swagger Theme
   ======================================================== */

/* 1. Global Reset & Typography */
body {
    background-color: #f8fafc !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important;
    color: #1e293b !important;
    margin: 0;
    padding: 0;
}

.swagger-ui {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important;
    color: #1e293b !important;
}

.swagger-ui .wrapper {
    max-width: 1200px !important;
    padding: 24px 32px !important;
    margin: 0 auto !important;
}

/* 2. Topbar Header Branding */
.swagger-ui .topbar {
    background-color: #0f172a !important; /* Deep Navy matching frontend sidebar */
    border-bottom: 1px solid #1e293b !important;
    padding: 14px 0 !important;
    box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1) !important;
}

.swagger-ui .topbar .topbar-wrapper {
    max-width: 1200px !important;
    padding: 0 32px !important;
    margin: 0 auto !important;
    display: flex !important;
    align-items: center !important;
}

.swagger-ui .topbar .topbar-wrapper .link {
    display: flex !important;
    align-items: center !important;
    gap: 12px !important;
    text-decoration: none !important;
}

.swagger-ui .topbar .topbar-wrapper .link::after {
    content: "Tri9T-CT200 Document Intelligence API";
    color: #ffffff;
    font-size: 15px;
    font-weight: 700;
    letter-spacing: -0.01em;
}

.swagger-ui .topbar .download-url-wrapper {
    display: flex !important;
    align-items: center !important;
}

/* 3. API Information Hero Card */
.swagger-ui .info {
    margin: 20px 0 28px 0 !important;
    background: #ffffff !important;
    padding: 28px !important;
    border-radius: 14px !important;
    border: 1px solid #e2e8f0 !important;
    box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.04) !important;
}

.swagger-ui .info .title {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    font-size: 24px !important;
    font-weight: 800 !important;
    color: #0f172a !important;
    letter-spacing: -0.02em !important;
    margin-bottom: 8px !important;
}

.swagger-ui .info .title small.version-stamp {
    background-color: #4f46e5 !important; /* Indigo accent */
    border-radius: 9999px !important;
    padding: 3px 10px !important;
    top: -2px !important;
    margin-left: 10px !important;
}

.swagger-ui .info .title small.version-stamp pre.version {
    color: #ffffff !important;
    font-family: ui-monospace, SFMono-Regular, monospace !important;
    font-size: 11px !important;
    font-weight: 600 !important;
}

.swagger-ui .info p {
    font-size: 13.5px !important;
    color: #475569 !important;
    line-height: 1.6 !important;
    margin: 8px 0 !important;
}

.swagger-ui .info a {
    color: #4f46e5 !important;
    text-decoration: none !important;
    font-weight: 500 !important;
}

.swagger-ui .info a:hover {
    text-decoration: underline !important;
}

.swagger-ui .info .base-url {
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace !important;
    font-size: 12px !important;
    color: #64748b !important;
    background: #f1f5f9 !important;
    padding: 4px 8px !important;
    border-radius: 6px !important;
    display: inline-block !important;
    margin-top: 6px !important;
}

/* 4. Filter & Search Controls */
.swagger-ui .filter-container {
    background: #ffffff !important;
    padding: 12px 18px !important;
    border-radius: 12px !important;
    border: 1px solid #e2e8f0 !important;
    box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.03) !important;
    margin-bottom: 24px !important;
}

.swagger-ui .filter-container .operation-filter-input {
    border: 1px solid #cbd5e1 !important;
    border-radius: 8px !important;
    padding: 8px 14px !important;
    font-size: 13px !important;
    outline: none !important;
    transition: all 0.15s ease !important;
    color: #1e293b !important;
    width: 100% !important;
    box-sizing: border-box !important;
}

.swagger-ui .filter-container .operation-filter-input:focus {
    border-color: #6366f1 !important;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15) !important;
}

/* 5. Tag & Section Groups */
.swagger-ui .opblock-tag-section {
    margin-bottom: 28px !important;
}

.swagger-ui .opblock-tag {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    font-size: 17px !important;
    font-weight: 700 !important;
    color: #0f172a !important;
    border-bottom: 2px solid #e2e8f0 !important;
    padding: 10px 0 !important;
    margin-bottom: 12px !important;
}

.swagger-ui .opblock-tag:hover {
    background: transparent !important;
}

.swagger-ui .opblock-tag small {
    font-size: 12px !important;
    color: #64748b !important;
    font-weight: 400 !important;
    margin-left: 8px !important;
}

/* 6. Opblock Cards (Endpoints) */
.swagger-ui .opblock {
    background: #ffffff !important;
    border-radius: 10px !important;
    margin: 0 0 10px 0 !important;
    box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.03) !important;
    border: 1px solid #e2e8f0 !important;
    transition: all 0.18s ease-in-out !important;
    overflow: hidden !important;
}

.swagger-ui .opblock:hover {
    box-shadow: 0 3px 6px -1px rgba(0, 0, 0, 0.06) !important;
}

.swagger-ui .opblock .opblock-summary {
    padding: 8px 14px !important;
    display: flex !important;
    align-items: center !important;
    cursor: pointer !important;
}

.swagger-ui .opblock .opblock-summary-method {
    border-radius: 6px !important;
    font-weight: 700 !important;
    font-size: 11.5px !important;
    min-width: 68px !important;
    text-align: center !important;
    padding: 6px 10px !important;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace !important;
    text-shadow: none !important;
    letter-spacing: 0.04em !important;
}

.swagger-ui .opblock .opblock-summary-path {
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    color: #0f172a !important;
    padding: 0 10px !important;
}

.swagger-ui .opblock .opblock-summary-path__deprecated {
    text-decoration: line-through !important;
    color: #94a3b8 !important;
}

.swagger-ui .opblock .opblock-summary-description {
    font-size: 12px !important;
    color: #64748b !important;
    font-weight: 400 !important;
}

/* 7. HTTP Method Tailored Accents */
/* GET: Classic Blue */
.swagger-ui .opblock.opblock-get {
    border-color: #bfdbfe !important;
}
.swagger-ui .opblock.opblock-get .opblock-summary {
    background-color: #f8faff !important;
}
.swagger-ui .opblock.opblock-get .opblock-summary-method {
    background-color: #2563eb !important;
    color: #ffffff !important;
}

/* POST: Emerald Green */
.swagger-ui .opblock.opblock-post {
    border-color: #bbf7d0 !important;
}
.swagger-ui .opblock.opblock-post .opblock-summary {
    background-color: #f6fdf9 !important;
}
.swagger-ui .opblock.opblock-post .opblock-summary-method {
    background-color: #059669 !important;
    color: #ffffff !important;
}

/* PUT: Warm Amber */
.swagger-ui .opblock.opblock-put {
    border-color: #fde68a !important;
}
.swagger-ui .opblock.opblock-put .opblock-summary {
    background-color: #fffdf5 !important;
}
.swagger-ui .opblock.opblock-put .opblock-summary-method {
    background-color: #d97706 !important;
    color: #ffffff !important;
}

/* DELETE: Rose Crimson */
.swagger-ui .opblock.opblock-delete {
    border-color: #fecdd3 !important;
}
.swagger-ui .opblock.opblock-delete .opblock-summary {
    background-color: #fff9f9 !important;
}
.swagger-ui .opblock.opblock-delete .opblock-summary-method {
    background-color: #dc2626 !important;
    color: #ffffff !important;
}

/* PATCH: Teal */
.swagger-ui .opblock.opblock-patch {
    border-color: #99f6e4 !important;
}
.swagger-ui .opblock.opblock-patch .opblock-summary {
    background-color: #f4fcfb !important;
}
.swagger-ui .opblock.opblock-patch .opblock-summary-method {
    background-color: #0d9488 !important;
    color: #ffffff !important;
}

/* 8. Expanded Opblock Body */
.swagger-ui .opblock-body {
    background: #ffffff !important;
    padding: 20px 24px !important;
    border-top: 1px solid #f1f5f9 !important;
}

.swagger-ui .opblock-section-header {
    background: #f8fafc !important;
    border-radius: 8px !important;
    padding: 8px 12px !important;
    min-height: auto !important;
    border: 1px solid #e2e8f0 !important;
    margin-bottom: 12px !important;
}

.swagger-ui .opblock-section-header h4 {
    font-size: 12.5px !important;
    font-weight: 700 !important;
    color: #334155 !important;
    font-family: inherit !important;
    letter-spacing: -0.01em !important;
}

/* Tables in Parameters */
.swagger-ui table.parameters {
    border-collapse: collapse !important;
    width: 100% !important;
    margin: 8px 0 16px 0 !important;
}

.swagger-ui table.parameters th {
    font-size: 11.5px !important;
    color: #64748b !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    border-bottom: 2px solid #e2e8f0 !important;
    padding: 8px !important;
    text-align: left !important;
}

.swagger-ui table.parameters td {
    padding: 10px 8px !important;
    border-bottom: 1px solid #f1f5f9 !important;
    font-size: 12.5px !important;
}

.swagger-ui .parameter__name {
    font-family: ui-monospace, SFMono-Regular, monospace !important;
    font-weight: 700 !important;
    font-size: 12px !important;
    color: #0f172a !important;
}

.swagger-ui .parameter__type {
    font-family: ui-monospace, monospace !important;
    font-size: 11px !important;
    color: #64748b !important;
}

.swagger-ui .parameter__in {
    font-size: 11px !important;
    color: #94a3b8 !important;
    font-style: italic !important;
}

/* 9. Buttons & Interactive Controls */
.swagger-ui .btn.try-out__btn {
    border: 1px solid #cbd5e1 !important;
    border-radius: 6px !important;
    background: #ffffff !important;
    color: #334155 !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    padding: 5px 14px !important;
    transition: all 0.15s ease !important;
    box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.03) !important;
}

.swagger-ui .btn.try-out__btn:hover {
    background: #f8fafc !important;
    border-color: #94a3b8 !important;
}

.swagger-ui .btn.execute {
    background-color: #4f46e5 !important; /* Indigo accent */
    border-color: #4f46e5 !important;
    color: #ffffff !important;
    border-radius: 6px !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    padding: 7px 18px !important;
    box-shadow: 0 1px 2px 0 rgba(79, 70, 229, 0.2) !important;
    transition: all 0.15s ease !important;
}

.swagger-ui .btn.execute:hover {
    background-color: #4338ca !important;
    border-color: #4338ca !important;
}

.swagger-ui .btn.cancel {
    border: 1px solid #fecdd3 !important;
    background: #ffffff !important;
    color: #dc2626 !important;
    border-radius: 6px !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    padding: 5px 14px !important;
}

.swagger-ui .btn.cancel:hover {
    background: #fff1f2 !important;
}

/* 10. Code Highlighting & Response Boxes */
.swagger-ui .highlight-code,
.swagger-ui .microlight {
    border-radius: 8px !important;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace !important;
    font-size: 12px !important;
    background: #0f172a !important; /* Deep Navy Editor */
    color: #f8fafc !important;
    border: 1px solid #1e293b !important;
    padding: 12px !important;
}

.swagger-ui .response-col_status {
    font-family: ui-monospace, monospace !important;
    font-weight: 700 !important;
    font-size: 13px !important;
    color: #0f172a !important;
}

.swagger-ui .responses-inner {
    padding: 10px 0 !important;
}

/* 11. Bottom Schemas / Models */
.swagger-ui section.models {
    border: 1px solid #e2e8f0 !important;
    border-radius: 14px !important;
    background: #ffffff !important;
    box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.04) !important;
    margin-top: 36px !important;
    overflow: hidden !important;
}

.swagger-ui section.models h4 {
    color: #0f172a !important;
    font-family: inherit !important;
    font-weight: 700 !important;
    font-size: 16px !important;
    padding: 16px 20px !important;
    border-bottom: 1px solid #f1f5f9 !important;
}

.swagger-ui section.models .model-container {
    background: #ffffff !important;
    margin: 8px 16px !important;
    border-radius: 8px !important;
    border: 1px solid #f1f5f9 !important;
}

.swagger-ui .model-title {
    font-family: ui-monospace, SFMono-Regular, monospace !important;
    font-size: 13px !important;
    font-weight: 700 !important;
    color: #0f172a !important;
}
"""


def get_custom_swagger_css() -> str:
    """Returns the CSS string for Swagger UI customization."""
    return SWAGGER_CUSTOM_CSS
