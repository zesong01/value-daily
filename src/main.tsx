import React from 'react';
import {createRoot} from 'react-dom/client';
import Reader from './reader';
import './style.css';
import initial from '../public/reports/2026-10-15-AM.json';
import type {Report} from './report-schema';
createRoot(document.getElementById('root')!).render(<React.StrictMode><Reader initial={initial as Report}/></React.StrictMode>);
