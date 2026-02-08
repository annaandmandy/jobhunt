import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import TextareaAutosize from 'react-textarea-autosize';
import { Copy, Download, FileText, Briefcase, Wand2 } from 'lucide-react';
import './ReviewEdit.css';

interface Drafts {
    resume: string;
    coverLetter: string;
}

const ReviewEdit = () => {
    const [activeTab, setActiveTab] = useState<'input' | 'edit'>('input');
    const [jobDescription, setJobDescription] = useState('');
    const [isGenerating, setIsGenerating] = useState(false);
    const [drafts, setDrafts] = useState<Drafts>({ resume: '', coverLetter: '' });
    const [activeEditPane, setActiveEditPane] = useState<'resume' | 'coverLetter'>('resume');

    // Mock scraping logic (replace with actual chrome.scripting later)
    useEffect(() => {
        const scrapeJD = async () => {
            // In a real extension, we'd use chrome.tabs.query and chrome.scripting.executeScript
            // utilizing a content script to extract text.
            // For now, we'll just placeholder or try to read from clipboard as a fallback fallback
            console.log('Attempting to scrape JD...');
        };
        scrapeJD();
    }, []);

    const handleGenerate = async () => {
        setIsGenerating(true);
        try {
            const response = await fetch('http://localhost:8000/api/v1/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ job_description: jobDescription }),
            });

            if (!response.ok) throw new Error('Generation failed');

            const data = await response.json();
            setDrafts({
                resume: data.resume,
                coverLetter: data.coverLetter
            });
            setActiveTab('edit');
        } catch (error) {
            console.error('Error generating drafts:', error);
            alert('Failed to generate drafts. Ensure backend is running.');
        } finally {
            setIsGenerating(false);
        }
    };

    const copyToClipboard = (text: string) => {
        navigator.clipboard.writeText(text);
        // TODO: Add toast notification
    };

    const downloadPDF = async () => {
        try {
            const type = activeEditPane === 'resume' ? 'resume' : 'cover_letter';
            const content = activeEditPane === 'resume' ? drafts.resume : drafts.coverLetter;

            const response = await fetch('http://localhost:8000/api/v1/export-pdf', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    content,
                    type
                }),
            });

            if (!response.ok) throw new Error('PDF Export failed');

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${type === 'resume' ? 'Resume' : 'CoverLetter'}.pdf`;
            document.body.appendChild(a);
            a.click();
            a.remove();
        } catch (error) {
            console.error('Error downloading PDF:', error);
            alert('Failed to download PDF.');
        }
    };

    return (
        <div className="review-edit-container">
            <div className="tabs-header">
                <button
                    className={`tab-btn ${activeTab === 'input' ? 'active' : ''}`}
                    onClick={() => setActiveTab('input')}
                >
                    <Briefcase size={16} /> Input
                </button>
                <button
                    className={`tab-btn ${activeTab === 'edit' ? 'active' : ''}`}
                    onClick={() => setActiveTab('edit')}
                    disabled={!drafts.resume}
                >
                    <FileText size={16} /> Edit & Export
                </button>
            </div>

            <div className="tab-content">
                <AnimatePresence mode="wait">
                    {activeTab === 'input' ? (
                        <motion.div
                            key="input"
                            initial={{ opacity: 0, x: -20 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: 20 }}
                            className="input-pane"
                        >
                            <h3>Job Description</h3>
                            <TextareaAutosize
                                minRows={10}
                                placeholder="Paste Job Description here..."
                                value={jobDescription}
                                onChange={(e) => setJobDescription(e.target.value)}
                                className="jd-input"
                            />
                            <button
                                className="generate-btn"
                                onClick={handleGenerate}
                                disabled={!jobDescription || isGenerating}
                            >
                                {isGenerating ? (
                                    <span className="loading-spinner">Generating...</span>
                                ) : (
                                    <>
                                        <Wand2 size={18} /> Generate Drafts
                                    </>
                                )}
                            </button>
                        </motion.div>
                    ) : (
                        <motion.div
                            key="edit"
                            initial={{ opacity: 0, x: 20 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -20 }}
                            className="edit-pane"
                        >
                            <div className="edit-controls">
                                <div className="pane-switcher">
                                    <button
                                        className={activeEditPane === 'resume' ? 'active' : ''}
                                        onClick={() => setActiveEditPane('resume')}
                                    >
                                        Resume
                                    </button>
                                    <button
                                        className={activeEditPane === 'coverLetter' ? 'active' : ''}
                                        onClick={() => setActiveEditPane('coverLetter')}
                                    >
                                        Cover Letter
                                    </button>
                                </div>
                                <div className="action-buttons">
                                    <button
                                        onClick={() => copyToClipboard(activeEditPane === 'resume' ? drafts.resume : drafts.coverLetter)}
                                        title="Copy to Clipboard"
                                    >
                                        <Copy size={16} />
                                    </button>
                                    <button onClick={downloadPDF} title="Download PDF">
                                        <Download size={16} />
                                    </button>
                                </div>
                            </div>

                            <TextareaAutosize
                                value={activeEditPane === 'resume' ? drafts.resume : drafts.coverLetter}
                                onChange={(e) => setDrafts({
                                    ...drafts,
                                    [activeEditPane]: e.target.value
                                })}
                                className="editor-textarea"
                                minRows={15}
                            />
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </div>
    );
};

export default ReviewEdit;
