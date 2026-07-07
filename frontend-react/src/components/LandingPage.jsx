import React, { useState } from 'react';
import Login from './Login';
import './LandingPage.css';

export default function LandingPage() {
  const [showAuthModal, setShowAuthModal] = useState(null); // 'login' | 'signup' | null
  const appName = import.meta.env.VITE_APP_NAME || 'Milvus RAG';

  // Helper to scroll to sections smoothly
  const scrollToSection = (id) => {
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <div className="landing-container">
      {/* --- STICKY NAVBAR --- */}
      <header className="landing-navbar">
        <div className="navbar-logo" onClick={() => scrollToSection('top')}>
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

      {/* --- HERO SECTION --- */}
      <section className="hero-section">
        <div className="hero-content">
          <div className="hero-badge">
            <span className="badge-icon">⚡</span>
            <span>Now with Hybrid Dense-Sparse Search</span>
          </div>

          <h1 className="hero-title">
            Understand Documents, <br />
            <span className="gradient-text">Just Ask.</span>
          </h1>

          <p className="hero-description">
            Upload your technical manuals, contracts, or reports. Our system parses structures,
            extracts tables, indexes dense semantics, and maps sparse keywords. Ask questions in plain language 
            and get verified, source-cited responses in seconds.
          </p>

          <div className="hero-ctas">
            <button onClick={() => setShowAuthModal('signup')} className="btn-hero-primary">
              Get Started Free →
            </button>
            <button onClick={() => scrollToSection('features')} className="btn-hero-secondary">
              View Features
            </button>
          </div>

          <div className="hero-social-info">
            <div className="social-users">
              <span className="users-count">Hundreds of users</span> worldwide
            </div>
            <div className="social-benefits">
              <span>Free tier</span> • <span>No credit card</span> • <span>Cancel anytime</span>
            </div>
          </div>
        </div>

        {/* --- RIGHT COLUMN: APP MOCKUP --- */}
        <div className="hero-mockup-container">
          <div className="mac-window">
            <div className="window-header">
              <div className="window-dots">
                <span className="dot red"></span>
                <span className="dot yellow"></span>
                <span className="dot green"></span>
              </div>
              <div className="window-title">rag-workspace (active)</div>
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
                    <span className="mockup-bot-name">Document Assistant</span>
                    <span className="mockup-bot-status">ready</span>
                  </div>
                </div>

                <div className="mockup-messages">
                  <div className="mockup-msg user">
                    <div className="msg-bubble">
                      Explain the Siemens Turbine cooling valve safety parameters.
                    </div>
                  </div>

                  <div className="mockup-retrieval-status">
                    <div className="spinner"></div>
                    <span>Searching Milvus (Dense + Sparse Hybrid Search)...</span>
                  </div>

                  <div className="mockup-msg bot">
                    <div className="msg-bubble">
                      Based on the Siemens OEM Manual, the cooling valve must trigger at 
                      <strong> 150°C</strong> or if pressure exceeds <strong>12.4 bar</strong>. 
                      A redundant secondary bypass opens in 45 milliseconds.
                      
                      <div className="mockup-sources">
                        <span className="source-tag">siemens-manual.pdf • Page 24</span>
                        <span className="source-tag">spec-sheet-v2.pdf • Page 3</span>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="mockup-chat-input">
                  <div className="input-placeholder">Ask about your documents...</div>
                  <div className="mockup-send-btn"></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* --- TRUSTED BY ROW --- */}
      <section className="trusted-section">
        <p className="trusted-title">TRUSTED BY TEAMS AT</p>
        <div className="trusted-logos">
          <div className="logo-item">CloudNine</div>
          <div className="logo-item">DataPulse</div>
          <div className="logo-item">SwiftOps</div>
          <div className="logo-item">BrightPath</div>
          <div className="logo-item">CoreStack</div>
          <div className="logo-item">Zenith</div>
          <div className="logo-item">TechFlow</div>
          <div className="logo-item">NovaDesk</div>
        </div>
      </section>

      {/* --- FEATURES GRID --- */}
      <section id="features" className="features-section">
        <h2 className="section-title">Everything You Need to <span className="gradient-text">Understand Data</span></h2>
        <p className="section-subtitle">Structure-aware ingestion, multi-vector retrieval, and lightning-fast pipelines.</p>

        <div className="features-grid">
          {/* Card 1 */}
          <div className="feature-card">
            <div className="card-header">
              <div className="feature-icon bg-cyan">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="16" y1="13" x2="8" y2="13" />
                  <line x1="16" y1="17" x2="8" y2="17" />
                  <polyline points="10 9 9 9 8 9" />
                </svg>
              </div>
              <h3 className="card-title">Structure-Aware Parsing</h3>
            </div>
            <p className="card-text">
              Extract headers, logical section trees, tables, and image captions cleanly using the Docling pipeline. No more broken layout summaries or scrambled tables.
            </p>
            <div className="card-mockup parsing-mockup">
              <div className="parsing-line"><span>[Header 1 &gt; Safety Settings]</span></div>
              <div className="parsing-table">
                <div className="table-header"><span>Temp</span><span>Limit</span></div>
                <div className="table-row"><span>150°C</span><span>45ms</span></div>
              </div>
            </div>
          </div>

          {/* Card 2 */}
          <div className="feature-card">
            <div className="card-header">
              <div className="feature-icon bg-blue">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="11" cy="11" r="8" />
                  <line x1="21" y1="21" x2="16.65" y2="16.65" />
                  <line x1="11" y1="8" x2="11" y2="14" />
                  <line x1="8" y1="11" x2="14" y2="11" />
                </svg>
              </div>
              <h3 className="card-title">Hybrid Search &amp; Reranking</h3>
            </div>
            <p className="card-text">
              Combines Milvus dense semantic embeddings (Gemini/OpenAI) and sparse BM25 keyword matrices. Reranks final results using Cross-Encoders for maximal citation accuracy.
            </p>
            <div className="card-mockup search-mockup">
              <div className="search-pill sparse">Sparse Keywords: "safety valve limit"</div>
              <div className="search-plus">+</div>
              <div className="search-pill dense">Dense Semantics: [0.12, -0.45, 0.89...]</div>
              <div className="search-result">Reciprocal Rank Fusion (RRF) -&gt; Match: 99.4%</div>
            </div>
          </div>
        </div>
      </section>

      {/* --- HOW IT WORKS SECTION --- */}
      <section id="how-it-works" className="how-it-works-section">
        <h2 className="section-title">How It Works</h2>
        <p className="section-subtitle">From document upload to verified answers in four easy steps.</p>

        <div className="steps-container">
          <div className="step-item">
            <div className="step-number">01</div>
            <h4 className="step-title">Upload Documents</h4>
            <p className="step-description">Drop PDFs or technical manuals directly into the secure ingestion workspace.</p>
            <div className="step-badge">PDF support</div>
          </div>

          <div className="step-item">
            <div className="step-number">02</div>
            <h4 className="step-title">Asynchronous Parsing</h4>
            <p className="step-description">Redis queue simple workers parse headers, sections, and complex metadata tables.</p>
            <div className="step-badge">Redis simple queue</div>
          </div>

          <div className="step-item">
            <div className="step-number">03</div>
            <h4 className="step-title">Vector Indexing</h4>
            <p className="step-description">Embeddings are indexed dynamically into Milvus Lite/Standalone vector storage.</p>
            <div className="step-badge">Milvus Lite</div>
          </div>

          <div className="step-item">
            <div className="step-number">04</div>
            <h4 className="step-title">Ask &amp; Cite</h4>
            <p className="step-description">Ask any question. The assistant retrieves, reranks, answers, and cites page locations.</p>
            <div className="step-badge">Deep citation</div>
          </div>
        </div>
      </section>

      {/* --- PRICING & CTA --- */}
      <section id="pricing" className="cta-section">
        <div className="cta-box">
          <h2 className="cta-title">Ready to unlock document intelligence?</h2>
          <p className="cta-subtitle">Start processing PDFs and querying your knowledge base instantly.</p>
          <button onClick={() => setShowAuthModal('signup')} className="btn-cta">
            Get Started Free
          </button>
        </div>
      </section>

      {/* --- FOOTER --- */}
      <footer id="support" className="landing-footer">
        <div className="footer-columns">
          <div className="footer-column brand">
            <div className="navbar-logo" onClick={() => scrollToSection('top')}>
              <img src="/favicon.svg" alt="Logo" width="24" height="24" />
              <span className="navbar-title">{appName}</span>
            </div>
            <p className="brand-text">Production-grade Retrieval-Augmented Generation for technical manuals and enterprise PDFs.</p>
          </div>

          <div className="footer-column">
            <h4>Product</h4>
            <ul>
              <li><button onClick={() => scrollToSection('features')} className="footer-link">Features</button></li>
              <li><button onClick={() => scrollToSection('how-it-works')} className="footer-link">Retrieval Engine</button></li>
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
              <li><button onClick={() => alert(`${appName} is an open-source demonstration.`)} className="footer-link">About Us</button></li>
              <li><button onClick={() => alert("We're currently not hiring.")} className="footer-link">Careers</button></li>
              <li><button onClick={() => alert("Data stored locally. Firebase auth guidelines apply.")} className="footer-link">Privacy Policy</button></li>
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
