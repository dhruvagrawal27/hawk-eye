{{/*
=============================================================================
Hawk-Eye Helm template helpers.
Blueprint: Part 9.3 (residency) · Part 16 (RBI localization) ·
           Part 19.3 (zero-trust labels) · PLATFORM-9.
-----------------------------------------------------------------------------
Centralises naming and the MANDATORY residency labels so every workload is
labelled identically. `hawk-eye.residencyLabels` is the single point that
stamps `data-residency: in-india` + `region: ap-south-1` onto every pod and
object — the OPA/Conftest policy (deploy/k8s/policy/) fails the render if any
pod template is missing them.
=============================================================================
*/}}

{{/* Chart name, sanitised to 63 chars (DNS-1123). */}}
{{- define "hawk-eye.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/* Fully-qualified release name prefix: <release>-<chart> (or fullnameOverride). */}}
{{- define "hawk-eye.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/* Chart label "name-version" for app.kubernetes.io/managed-by metadata. */}}
{{- define "hawk-eye.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Per-workload resource name. Call with a dict: (dict "ctx" $ "name" $workloadName).
Produces "<fullname>-<workload>" e.g. "hawk-eye-kafka".
*/}}
{{- define "hawk-eye.workloadName" -}}
{{- printf "%s-%s" (include "hawk-eye.fullname" .ctx) .name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
MANDATORY RESIDENCY LABELS (Part 9.3 / Part 16).
Applied to EVERY object's metadata.labels AND every pod template.labels.
The OPA residency policy asserts these exact keys/values on every pod.
*/}}
{{- define "hawk-eye.residencyLabels" -}}
data-residency: {{ .Values.global.residency.dataResidency | quote }}
region: {{ .Values.global.residency.region | quote }}
{{- end -}}

{{/*
Common labels — recommended app.kubernetes.io/* set + residency labels.
Call with (dict "ctx" $ "name" $workloadName "tier" $tier).
*/}}
{{- define "hawk-eye.labels" -}}
helm.sh/chart: {{ include "hawk-eye.chart" .ctx }}
app.kubernetes.io/managed-by: {{ .ctx.Release.Service }}
app.kubernetes.io/part-of: hawk-eye
app.kubernetes.io/version: {{ .ctx.Chart.AppVersion | quote }}
{{ include "hawk-eye.selectorLabels" . }}
{{- if .tier }}
app.kubernetes.io/tier: {{ .tier | quote }}
{{- end }}
{{ include "hawk-eye.residencyLabels" .ctx }}
{{- end -}}

{{/*
Selector labels — the STABLE subset used by Deployment selectors + Services +
NetworkPolicy podSelectors. Never include version/residency churn here.
Call with (dict "ctx" $ "name" $workloadName).
*/}}
{{- define "hawk-eye.selectorLabels" -}}
app.kubernetes.io/name: {{ include "hawk-eye.name" .ctx }}
app.kubernetes.io/instance: {{ .ctx.Release.Name }}
app.kubernetes.io/component: {{ .name | quote }}
{{- end -}}

{{/*
Image pull policy (workload override -> global default).
Call with (dict "ctx" $ "wl" $workloadSpec).
*/}}
{{- define "hawk-eye.imagePullPolicy" -}}
{{- default .ctx.Values.global.imagePullPolicy .wl.imagePullPolicy -}}
{{- end -}}

{{/*
Pod-level securityContext = global default merged with per-workload override.
Call with (dict "ctx" $ "wl" $workloadSpec).
*/}}
{{- define "hawk-eye.podSecurityContext" -}}
{{- $base := .ctx.Values.global.podSecurityContext | default dict -}}
{{- $ovr := .wl.security | default dict -}}
{{- toYaml (merge (deepCopy $ovr) $base) -}}
{{- end -}}

{{/*
Container-level securityContext (least-privilege; Part 19.3).
Call with (dict "ctx" $).
*/}}
{{- define "hawk-eye.containerSecurityContext" -}}
{{- toYaml .ctx.Values.global.containerSecurityContext -}}
{{- end -}}
