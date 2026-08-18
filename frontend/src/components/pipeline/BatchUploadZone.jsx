import React, { useRef, useState } from 'react';
import { pipelineApi } from '../../api/index';

const SOURCE_SYSTEMS = [
  { value: 'CMS_DE_SynPUF',   label: 'CMS DE-SynPUF' },
  { value: 'CMS_LDS',         label: 'CMS Limited Data Set' },
  { value: 'EPIC_837',        label: 'EPIC Systems (837)' },
  { value: 'CERNER_EHR',      label: 'Cerner Millennium EHR' },
  { value: 'OUTPATIENT_BATCH',label: 'Outpatient Clearinghouse' },
];

export function BatchUploadZone({ onUploadStart, onUploadSuccess, onUploadError, isUploading = false }) {
  const [dragOver, setDragOver] = useState(false);
  const [sourceSystem, setSourceSystem] = useState('CMS_DE_SynPUF');
  const [createdBy, setCreatedBy] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [localError, setLocalError] = useState(null);
  const fileInputRef = useRef(null);

  const handleFile = (file) => {
    setLocalError(null);
    if (!file) return;
    if (!file.name.endsWith('.zip')) {
      setLocalError('Only .zip files are accepted. Please upload a ZIP containing inpatient.csv, outpatient.csv, and/or carrier.csv.');
      return;
    }
    setSelectedFile(file);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    handleFile(file);
  };

  const handleFileInput = (e) => {
    const file = e.target.files?.[0];
    handleFile(file);
    e.target.value = '';
  };

  const handleSubmit = async () => {
    if (!selectedFile) {
      setLocalError('Please select a ZIP file first.');
      return;
    }
    const formData = new FormData();
    formData.append('file', selectedFile);
    if (sourceSystem) formData.append('source_system', sourceSystem);
    if (createdBy) formData.append('created_by', createdBy);

    onUploadStart?.(selectedFile.name);

    try {
      const result = await pipelineApi.uploadZip(formData);
      setSelectedFile(null);
      setLocalError(null);
      onUploadSuccess?.(result);
    } catch (err) {
      const errMsg = err.message || 'Upload and pipeline execution failed.';
      setLocalError(errMsg);
      onUploadError?.(errMsg);
    }
  };

  return (
    <div className="bg-surface-container-lowest rounded-2xl p-6 shadow-sm border border-outline-variant/20 flex flex-col gap-4">
      {/* Header */}
      <div>
        <span className="font-mono text-xs font-semibold text-primary uppercase tracking-wider">
          Intake Feeds
        </span>
        <h3 className="font-manrope text-lg font-bold text-on-surface">
          Raw CMS Claims Upload
        </h3>
        <p className="text-xs text-on-surface-variant mt-0.5">
          Upload a ZIP containing raw pipe-delimited CMS claims files. The engine will normalize, score ML priorities, and generate AI clinical rationales.
        </p>
      </div>

      {/* Source System + Created By */}
      <div className="flex flex-col sm:flex-row gap-3">
        <select
          value={sourceSystem}
          onChange={(e) => setSourceSystem(e.target.value)}
          disabled={isUploading}
          className="flex-1 bg-surface-container text-on-surface font-mono text-xs px-3 py-2 rounded-lg border border-outline-variant/20 outline-none"
        >
          {SOURCE_SYSTEMS.map((s) => (
            <option key={s.value} value={s.value}>{s.label}</option>
          ))}
        </select>
        <input
          type="text"
          value={createdBy}
          onChange={(e) => setCreatedBy(e.target.value)}
          disabled={isUploading}
          placeholder="Auditor name / System ID"
          className="flex-1 bg-surface-container text-on-surface font-mono text-xs px-3 py-2 rounded-lg border border-outline-variant/20 outline-none placeholder:text-outline"
        />
      </div>

      {/* Drop Zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => !isUploading && fileInputRef.current?.click()}
        className={`relative border-2 border-dashed rounded-2xl p-8 flex flex-col items-center justify-center text-center cursor-pointer transition-all select-none ${
          dragOver
            ? 'border-primary bg-primary/5 scale-[1.01]'
            : selectedFile
              ? 'border-emerald-400 bg-emerald-50/30'
              : 'border-outline-variant/40 bg-surface-container-low hover:bg-surface-container'
        } ${isUploading ? 'pointer-events-none opacity-60' : ''}`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".zip"
          onChange={handleFileInput}
          disabled={isUploading}
          className="hidden"
        />

        <div className={`w-14 h-14 rounded-full flex items-center justify-center mb-3 transition-colors ${
          isUploading
            ? 'bg-primary/20 text-primary animate-spin'
            : selectedFile
              ? 'bg-emerald-100 text-emerald-600'
              : 'bg-primary/10 text-primary'
        }`}>
          <span className="material-symbols-outlined text-[30px]">
            {isUploading ? 'progress_activity' : selectedFile ? 'folder_zip' : 'cloud_upload'}
          </span>
        </div>

        {isUploading ? (
          <>
            <h4 className="font-manrope text-base font-bold text-primary animate-pulse">
              Running End-to-End Pipeline...
            </h4>
            <p className="text-xs text-on-surface-variant mt-1">
              Extracting claims, scoring 8-signals, running ML inference & LLM summarization.
            </p>
          </>
        ) : selectedFile ? (
          <>
            <h4 className="font-manrope text-base font-bold text-emerald-700">
              {selectedFile.name}
            </h4>
            <p className="text-xs text-on-surface-variant mt-1">
              {(selectedFile.size / 1024).toFixed(1)} KB — ready to process
            </p>
          </>
        ) : (
          <>
            <h4 className="font-manrope text-base font-bold text-on-surface">
              Drop ZIP file here
            </h4>
            <p className="text-xs text-on-surface-variant mt-1 max-w-xs">
              Supports <span className="font-mono text-primary font-bold">inpatient.csv</span>,{' '}
              <span className="font-mono text-primary font-bold">outpatient.csv</span>,{' '}
              <span className="font-mono text-primary font-bold">carrier.csv</span>
            </p>
            <span className="font-mono text-[10px] text-outline mt-3 uppercase tracking-wide">
              Pipe-delimited ( | ) · CMS Standard Format
            </span>
          </>
        )}
      </div>

      {/* Error Message */}
      {localError && (
        <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 text-xs flex items-start gap-2">
          <span className="material-symbols-outlined text-[16px] mt-0.5">error</span>
          <span>{localError}</span>
        </div>
      )}

      {/* What's inside the ZIP pills */}
      <div className="flex flex-wrap gap-2">
        {[
          { file: 'inpatient.csv', label: 'INPATIENT (UB-04)', color: 'bg-blue-50 text-blue-700 border-blue-200' },
          { file: 'outpatient.csv', label: 'OUTPATIENT (837I)', color: 'bg-violet-50 text-violet-700 border-violet-200' },
          { file: 'carrier.csv', label: 'CARRIER (CMS-1500)', color: 'bg-amber-50 text-amber-700 border-amber-200' },
          { file: 'pde.csv', label: 'PDE (Rx)', color: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
        ].map(({ file, label, color }) => (
          <span
            key={file}
            className={`font-mono text-[10px] px-2 py-1 rounded-md border font-semibold uppercase tracking-wide ${color}`}
          >
            {file}
            <span className="opacity-60 font-normal ml-1 normal-case">{label}</span>
          </span>
        ))}
      </div>

      {/* Action Button */}
      <button
        onClick={handleSubmit}
        disabled={isUploading || !selectedFile}
        className={`w-full py-3 rounded-xl font-manrope font-bold text-sm flex items-center justify-center gap-2 transition-all ${
          isUploading || !selectedFile
            ? 'bg-outline/20 text-on-surface-variant cursor-not-allowed'
            : 'bg-primary text-on-primary hover:bg-primary/90 active:scale-[0.98] shadow-sm'
        }`}
      >
        <span className="material-symbols-outlined text-[20px]">
          {isUploading ? 'sync' : 'rocket_launch'}
        </span>
        {isUploading
          ? 'Executing Pipeline (Preprocessing → ML → LLM)...'
          : `Run Full Pipeline${selectedFile ? ` · ${selectedFile.name}` : ''}`}
      </button>
    </div>
  );
}
