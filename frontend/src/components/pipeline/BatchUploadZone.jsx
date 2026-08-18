import React, { useState } from 'react';
import { parseCsv } from '../../api/client';

export function BatchUploadZone({ onUpload, isUploading = false }) {
  const [dragOver, setDragOver] = useState(false);
  const [sourceSystem, setSourceSystem] = useState('EMR_CLINICAL_FEED');

  const processFile = async (file) => {
    if (!file) return;
    const text = await file.text();
    let claims = [];

    if (file.name.endsWith('.json')) {
      try {
        const parsed = JSON.parse(text);
        claims = Array.isArray(parsed) ? parsed : (parsed.claims || []);
      } catch (err) {
        alert('Invalid JSON file format: ' + err.message);
        return;
      }
    } else {
      claims = parseCsv(text);
    }

    if (claims.length === 0) {
      alert('File contains 0 valid claim records.');
      return;
    }

    onUpload({
      source_file: file.name,
      source_system: sourceSystem,
      claims,
    });
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      processFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileInput = (e) => {
    if (e.target.files && e.target.files[0]) {
      processFile(e.target.files[0]);
    }
  };

  return (
    <div className="bg-surface-container-lowest rounded-2xl p-6 shadow-sm border border-outline-variant/20 flex flex-col gap-4">
      <div className="flex justify-between items-center">
        <div>
          <span className="font-mono text-xs font-semibold text-primary uppercase tracking-wider">
            Intake Feeds
          </span>
          <h3 className="font-manrope text-lg font-bold text-on-surface">
            Incremental Claims Batch Upload
          </h3>
        </div>
        <select
          value={sourceSystem}
          onChange={(e) => setSourceSystem(e.target.value)}
          className="bg-surface-container text-on-surface font-mono text-xs px-3 py-1.5 rounded-lg border border-outline-variant/20 outline-none"
        >
          <option value="EMR_CLINICAL_FEED">EMR Clinical Feed</option>
          <option value="EPIC_SYSTEMS">EPIC Systems (837)</option>
          <option value="CERNER_EHR">Cerner Millenium EHR</option>
          <option value="OUTPATIENT_BATCH">Outpatient Clearinghouse</option>
        </select>
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={`relative border-2 border-dashed rounded-2xl p-8 flex flex-col items-center justify-center text-center cursor-pointer transition-all ${
          dragOver
            ? 'border-primary bg-primary/5 scale-[1.01]'
            : 'border-outline-variant/40 bg-surface-container-low hover:bg-surface-container-high'
        }`}
      >
        <input
          type="file"
          accept=".csv,.json"
          onChange={handleFileInput}
          disabled={isUploading}
          className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
        />

        <div className="w-14 h-14 rounded-full bg-primary/10 text-primary flex items-center justify-center mb-3">
          <span className="material-symbols-outlined text-[30px]">
            {isUploading ? 'hourglass_top' : 'cloud_upload'}
          </span>
        </div>

        <h4 className="font-manrope text-base font-bold text-on-surface">
          {isUploading ? 'Processing Claims Batch & Running Engine…' : 'Upload Claims Data'}
        </h4>
        <p className="text-xs text-on-surface-variant mt-1 max-w-sm">
          Drag and drop CSV or JSON claims files here, or <span className="text-primary font-bold">browse</span>.
        </p>
        <span className="font-mono text-[10px] text-outline mt-3">
          ACCEPTED: .CSV, .JSON (MAX 50,000 CLAIMS PER BATCH)
        </span>
      </div>
    </div>
  );
}
