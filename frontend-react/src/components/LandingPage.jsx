import React, { useState, useEffect } from 'react';
import Login from './Login';
import { PRIVACY_POLICY, PRIVACY_POLICY_META, ABOUT_US, ABOUT_US_META } from './policyContent';
import './LandingPage.css';

export default function LandingPage() {
  const [showAuthModal, setShowAuthModal] = useState(null); // 'login' | 'signup' | null
  const [currentPath, setCurrentPath] = useState(window.location.pathname);
  const appName = import.meta.env.VITE_APP_NAME || 'Milvus RAG';

  // Listen for browser back/forward navigation
  useEffect(() => {
    const handlePopState = () => setCurrentPath(window.location.pathname);
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  // Navigate to a new path using native browser history API
  const navigateTo = (path) => {
    window.history.pushState(null, '', path);
    setCurrentPath(path);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // Helper to scroll to sections smoothly
  const scrollToSection = (id) => {
    if (currentPath !== '/') {
      navigateTo('/');
      setTimeout(() => {
        const element = document.getElementById(id);
        if (element) element.scrollIntoView({ behavior: 'smooth' });
      }, 100);
      return;
    }
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <div className="landing-container">
      {/* --- STICKY NAVBAR --- */}
      <header className="landing-navbar">
        <div className="navbar-logo" onClick={() => navigateTo('/')}>
          <img src="/favicon.svg" alt="Logo" width="28" height="28" />
          <span className="navbar-title">{appName}</span>
        </div>

        <nav className="navbar-links">
          <button onClick={() => scrollToSection('features')} className="nav-link">Features</button>
          <button onClick={() => scrollToSection('how-it-works')} className="nav-link">How It Works</button>
          <button onClick={() => scrollToSection('pricing')} className="nav-link">Pricing</button>
          <button onClick={() => scrollToSection('support')} className="nav-link">Support</button>
        </nav>

        <div className="navbar-actions">
          <button onClick={() => setShowAuthModal('login')} className="btn-signin">Sign In</button>
          <button onClick={() => setShowAuthModal('signup')} className="btn-getstarted">Get Started</button>
        </div>
      </header>

      {/* --- POLICY PAGES --- */}
      {currentPath === '/privacy' && (
        <div className="policy-page-wrapper">
          <div className="policy-page-container">
            <button className="policy-back-btn" onClick={() => navigateTo('/')}>
              ← Back to Home
            </button>

            <h1 className="policy-page-title">{PRIVACY_POLICY_META.title}</h1>

            <div className="policy-meta-row">
              <span className="policy-effective-date">Effective {PRIVACY_POLICY_META.effectiveDate}</span>
            </div>

            <hr className="policy-divider" />

            <div className="policy-content">
              {PRIVACY_POLICY.map((section) => (
                <div key={section.id} id={section.id} className="policy-section">
                  <h2>{section.title}</h2>
                  {section.paragraphs.map((text, i) => (
                    <p key={i} dangerouslySetInnerHTML={{ __html: text }} />
                  ))}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* --- ABOUT US PAGE --- */}
      {currentPath === '/about' && (
        <div className="policy-page-wrapper">
          <div className="policy-page-container">
            <button className="policy-back-btn" onClick={() => navigateTo('/')}>
              ← Back to Home
            </button>

            <h1 className="policy-page-title">{ABOUT_US_META.title}</h1>

            <div className="policy-meta-row">
              <span className="policy-effective-date">{ABOUT_US_META.subtitle}</span>
            </div>

            <hr className="policy-divider" />

            <div className="policy-content">
              {ABOUT_US.map((section) => (
                <div key={section.id} id={section.id} className="policy-section">
                  <h2>{section.title}</h2>
                  {section.paragraphs.map((text, i) => (
                    <p key={i} dangerouslySetInnerHTML={{ __html: text }} />
                  ))}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* --- MAIN LANDING PAGE CONTENT --- */}
      {currentPath === '/' && (
        <>
          {/* --- HERO SECTION --- */}
          <section className="hero-section">
            <div className="hero-content">
              <div className="hero-badge">
                <span className="badge-icon">⚡</span>
                <span>Industrial AI Agents • SAP ERP + OPC UA Telemetry</span>
              </div>

              <h1 className="hero-title">
                Industry Intelligence. <br />
                <span className="gradient-text">Let AI Agents Understand Your Machines.</span>
              </h1>

              <p className="hero-description">
                Connect your factory floor to intelligent AI agents. From real-time OPC UA telemetry and SAP ERP work orders to OEM manuals and safety SOPs—ask complex operational questions and get verified, ground-truth answers in seconds.
              </p>

              <div className="hero-ctas">
                <button onClick={() => setShowAuthModal('signup')} className="btn-hero-primary">
                  Launch Factory Agent →
                </button>
                <button onClick={() => scrollToSection('features')} className="btn-hero-secondary">
                  Explore Industrial Tools
                </button>
              </div>

              <div className="hero-social-info">
                <div className="social-users">
                  <span className="users-count">Built for Plant Engineers & Maintenance Ops</span>
                </div>
                <div className="social-benefits">
                  <span>Zero-Hallucination Guardrails</span> • <span>Read-Only Safety Protocol</span> • <span>SAP & OPC UA Ready</span>
                </div>
              </div>
            </div>

            {/* --- RIGHT COLUMN: INDUSTRIAL APP MOCKUP --- */}
            <div className="hero-mockup-container">
              <div className="mac-window">
                <div className="window-header">
                  <div className="window-dots">
                    <span className="dot red"></span>
                    <span className="dot yellow"></span>
                    <span className="dot green"></span>
                  </div>
                  <div className="window-title">industrial-agent (OPC UA + SAP Active)</div>
                </div>

                <div className="window-body">
                  <div className="mockup-sidebar">
                    <div className="mockup-logo-placeholder"></div>
                    <div className="mockup-nav-item active"></div>
                    <div className="mockup-nav-item"></div>
                    <div className="mockup-nav-item"></div>
                  </div>

                  <div className="mockup-chat-area">
                    <div className="mockup-chat-header">
                      <div className="mockup-avatar"></div>
                      <div className="mockup-header-text">
                        <span className="mockup-bot-name">Plant Multi-Agent Orchestrator</span>
                        <span className="mockup-bot-status">● connected to OPC UA &amp; SAP ERP</span>
                      </div>
                    </div>

                    <div className="mockup-messages">
                      <div className="mockup-msg user">
                        <div className="msg-bubble">
                          Turbine #4 vibration alert triggered. Check live telemetry, SAP stock for bearings, and OEM torque limits.
                        </div>
                      </div>

                      <div className="mockup-retrieval-status">
                        <div className="spinner"></div>
                        <span>Agent: OPC UA Read → SAP Stock → Milvus RAG Search...</span>
                      </div>

                      <div className="mockup-msg bot">
                        <div className="msg-bubble">
                          Turbine #4 vibration is currently elevated at <strong>4.8 mm/s</strong> (threshold: 3.5 mm/s). SAP records confirm <strong>14 units</strong> of replacement bearing BRG-6210-2RS in stock at Warehouse 1000. Per Siemens SOP Page 84, housing bolts must be torqued to <strong>120 Nm</strong>.

                          <div className="mockup-sources">
                            <span className="source-tag">OPC UA • Live Telemetry</span>
                            <span className="source-tag">SAP MM • Warehouse 1000</span>
                            <span className="source-tag">Siemens-SOP.pdf • Page 84</span>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="mockup-chat-input">
                      <div className="input-placeholder">Ask about telemetry, SAP stock, or SOPs...</div>
                      <div className="mockup-send-btn"></div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* --- ENTERPRISE CAPABILITIES --- */}
          <section id="features" className="features-section">
            <h2 className="section-title">Enterprise <span className="gradient-text">Capabilities</span></h2>
            <p className="section-subtitle">Built for industrial reliability and safety. Unifying plant telemetry, enterprise ERP, and technical manuals into zero-hallucination AI agents.</p>

            <div className="features-grid">
              {/* Card 1: IT/OT Orchestration */}
              <div className="feature-card">
                <div className="card-header">
                  <div className="feature-icon bg-cyan">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
                      <line x1="8" y1="21" x2="16" y2="21" />
                      <line x1="12" y1="17" x2="12" y2="21" />
                    </svg>
                  </div>
                  <h3 className="card-title">Unified IT &amp; OT Orchestration</h3>
                </div>
                <p className="card-text">
                  Query live machine telemetry via OPC UA alongside SAP ERP Plant Maintenance and stock inventory. Diagnose issues across IT and OT systems in a single prompt.
                </p>
                <div className="card-mockup parsing-mockup">
                  <div className="parsing-line"><span>&gt; OPC UA: ns=2;s=Turbine4.Vibration → 4.8 mm/s</span></div>
                  <div className="parsing-line"><span>&gt; SAP MM: BRG-6210-2RS → 14 units in stock</span></div>
                </div>
              </div>

              {/* Card 2: Structure-Aware RAG */}
              <div className="feature-card">
                <div className="card-header">
                  <div className="feature-icon bg-blue">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="11" cy="11" r="8" />
                      <line x1="21" y1="21" x2="16.65" y2="16.65" />
                    </svg>
                  </div>
                  <h3 className="card-title">Structure-Aware Technical RAG</h3>
                </div>
                <p className="card-text">
                  Parse complex tables, section hierarchies, and OEM specifications from technical manuals. Hybrid dense-sparse search with cross-encoder reranking delivers page-precise citations.
                </p>
                <div className="card-mockup search-mockup">
                  <div className="search-pill sparse">Query: "turbine cooling valve torque limit"</div>
                  <div className="search-plus">↓</div>
                  <div className="search-pill dense">Hybrid Search: Dense Semantics + Sparse Keywords</div>
                  <div className="search-result">Matched: Siemens-SOP.pdf • Page 84 (99.4%)</div>
                </div>
              </div>

              {/* Card 3: Guardrails & Safety Audits */}
              <div className="feature-card feature-card-full">
                <div className="card-header">
                  <div className="feature-icon bg-emerald">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                    </svg>
                  </div>
                  <h3 className="card-title">Production Guardrails &amp; Safety Audits</h3>
                </div>
                <p className="card-text">
                  Strict read-only tool execution whitelists, prompt injection defense, numerical grounding verification, and automated Permit-to-Work (PTW) safety compliance reviews against OEM manuals.
                </p>
              </div>
            </div>
          </section>

          {/* --- HOW IT WORKS SECTION --- */}
          <section id="how-it-works" className="how-it-works-section">
            <h2 className="section-title">How It Works</h2>
            <p className="section-subtitle">From plant systems to ground-truth intelligence in four steps.</p>

            <div className="steps-container">
              <div className="step-item">
                <div className="step-number">01</div>
                <h4 className="step-title">Connect &amp; Ingest</h4>
                <p className="step-description">Link OPC UA machine telemetry, SAP ERP endpoints, and upload OEM technical manuals and safety SOPs.</p>
                <div className="step-badge">System Integration</div>
              </div>

              <div className="step-item">
                <div className="step-number">02</div>
                <h4 className="step-title">Index &amp; Contextualize</h4>
                <p className="step-description">Background workers parse document structures, extract tables, and index OPC UA tag address spaces into private vector stores.</p>
                <div className="step-badge">Automated Pipeline</div>
              </div>

              <div className="step-item">
                <div className="step-number">03</div>
                <h4 className="step-title">Agent Orchestration</h4>
                <p className="step-description">AI agents query live machine sensors, inspect SAP stock inventory, and search technical manuals simultaneously.</p>
                <div className="step-badge">Live Diagnostic Loop</div>
              </div>

              <div className="step-item">
                <div className="step-number">04</div>
                <h4 className="step-title">Grounded Answers &amp; Audits</h4>
                <p className="step-description">Receive verified, page-cited answers and automated Permit-to-Work safety compliance reports.</p>
                <div className="step-badge">PTW Compliance</div>
              </div>
            </div>
          </section>

          {/* --- PRICING & CTA --- */}
          <section id="pricing" className="cta-section">
            <div className="cta-box">
              <h2 className="cta-title">Ready to bring intelligence to your plant floor?</h2>
              <p className="cta-subtitle">Connect SAP ERP, OPC UA telemetry, and OEM manuals to AI agents instantly.</p>
              <button onClick={() => setShowAuthModal('signup')} className="btn-cta">
                Launch Factory Agent
              </button>
            </div>
          </section>
        </>
      )}

      {/* --- FOOTER --- */}
      <footer id="support" className="landing-footer">
        <div className="footer-columns">
          <div className="footer-column brand">
            <div className="navbar-logo" onClick={() => navigateTo('/')}>
              <img src="/favicon.svg" alt="Logo" width="24" height="24" />
              <span className="navbar-title">{appName}</span>
            </div>
            <p className="brand-text">Enterprise Industrial AI Platform unifying SAP ERP, OPC UA machine telemetry, and technical SOPs into intelligent agents.</p>
          </div>

          <div className="footer-column">
            <h4>Product</h4>
            <ul>
              <li><button onClick={() => scrollToSection('features')} className="footer-link">Features</button></li>
              <li><button onClick={() => scrollToSection('how-it-works')} className="footer-link">Industrial Platform</button></li>
              <li><button onClick={() => scrollToSection('pricing')} className="footer-link">Pricing</button></li>
              <li><button onClick={() => scrollToSection('support')} className="footer-link">Changelog</button></li>
            </ul>
          </div>

          <div className="footer-column">
            <h4>Support</h4>
            <ul>
              <li><a href="https://milvus.io/docs" target="_blank" rel="noreferrer" className="footer-link">Documentation</a></li>
              <li><button onClick={() => alert("Please email support@example.com for inquiries.")} className="footer-link">Help Center</button></li>
              <li><button onClick={() => alert("All services online.")} className="footer-link">API Status</button></li>
            </ul>
          </div>

          <div className="footer-column">
            <h4>Company</h4>
            <ul>
              <li><button onClick={() => navigateTo('/about')} className="footer-link">About Us</button></li>
              <li><button onClick={() => alert("We're currently not hiring.")} className="footer-link">Careers</button></li>
              <li><button onClick={() => navigateTo('/privacy')} className="footer-link">Privacy Policy</button></li>
              <li><button onClick={() => alert("Terms of Service: For demonstration purposes only.")} className="footer-link">Terms of Service</button></li>
            </ul>
          </div>
        </div>

        <div className="footer-bottom">
          <p>© {new Date().getFullYear()} {appName}. All rights reserved.</p>
        </div>
      </footer>

      {/* --- AUTH MODAL OVERLAY --- */}
      {showAuthModal && (
        <div className="auth-modal-overlay" onClick={() => setShowAuthModal(null)}>
          <div className="auth-modal-content" onClick={(e) => e.stopPropagation()}>
            <Login initialSignUp={showAuthModal === 'signup'} onClose={() => setShowAuthModal(null)} />
          </div>
        </div>
      )}
    </div>
  );
}
