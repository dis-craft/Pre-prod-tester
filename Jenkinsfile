pipeline {
    agent any

    parameters {
        booleanParam(name: 'GENERATE_REMEDIATION', defaultValue: false, description: 'Generate/apply AI remediation and create a remediation PR')
        string(name: 'ORCHESTRATOR_REF', defaultValue: 'main', description: 'Pre-Prod-Orchestrator branch/tag/commit to use')
        string(name: 'BASE_BRANCH', defaultValue: 'main', description: 'Target branch for the remediation PR')
    }

    environment {
        GEMINI_API_KEY = credentials('preprod-gemini-api-key')
    }

    stages {
        stage('Checkout target repository') {
            steps {
                checkout scm
                sh 'git fetch --all --prune'
            }
        }

        stage('Capture exact change') {
            steps {
                sh '''
                    set -eu
                    BASE="${GIT_PREVIOUS_SUCCESSFUL_COMMIT:-${GIT_PREVIOUS_COMMIT:-HEAD~1}}"
                    git diff --text --unified=80 "$BASE" "$GIT_COMMIT" > "$WORKSPACE/.preprod-diff.patch"
                    mkdir -p "$WORKSPACE/.preprod"
                    cp "$WORKSPACE/.preprod-diff.patch" "$WORKSPACE/.preprod/scan.patch"
                '''
            }
        }

        stage('Checkout security engine') {
            steps {
                dir('.preprod-engine') {
                    git branch: params.ORCHESTRATOR_REF, credentialsId: 'github-token', url: 'https://github.com/dis-craft/Pre-Prod-Orchestrator.git'
                }
            }
        }

        stage('Initial scan') {
            steps {
                sh '''
                    set +e
                    PYTHONPATH="$WORKSPACE/.preprod-engine" python3 -m scanner --repo "$WORKSPACE" --diff "$WORKSPACE/.preprod-diff.patch" --model none --format all --output "$WORKSPACE/.preprod/baseline-scan" --quiet
                    rc=$?
                    set -e
                    if [ "$rc" -gt 1 ]; then exit "$rc"; fi
                    test -f "$WORKSPACE/.preprod/baseline-scan/findings.json"
                '''
                archiveArtifacts artifacts: '.preprod/baseline-scan/**/*', allowEmptyArchive: false
            }
        }

        stage('AI remediation') {
            when { expression { return params.GENERATE_REMEDIATION } }
            steps {
                sh '''
                    set -euo pipefail
                    PYTHONPATH="$WORKSPACE/.preprod-engine" python3 "$WORKSPACE/.preprod-engine/remediation/ci_entrypoint.py" --repo "$WORKSPACE" --findings "$WORKSPACE/.preprod/baseline-scan/findings.json" --output "$WORKSPACE/.preprod/remediation-result.json" --model "${GEMINI_MODEL:-gemini-3.6-flash}"
                '''
            }
        }

        stage('Tests') {
            when { expression { return params.GENERATE_REMEDIATION } }
            steps {
                sh '''
                    set -e
                    if [ -f package-lock.json ]; then npm ci; npm test --if-present
                    elif [ -f pyproject.toml ] || [ -f pytest.ini ] || [ -d tests ]; then python3 -m pytest -q
                    else echo "No generic test suite detected."; fi
                '''
            }
        }

        stage('Post-fix security scan') {
            when { expression { return params.GENERATE_REMEDIATION } }
            steps {
                sh '''
                    set +e
                    git diff --no-ext-diff --unified=80 HEAD -- . > "$WORKSPACE/.preprod/post-remediation.diff"
                    PYTHONPATH="$WORKSPACE/.preprod-engine" python3 -m scanner --repo "$WORKSPACE" --diff "$WORKSPACE/.preprod/post-remediation.diff" --model none --format all --output "$WORKSPACE/.preprod/post-remediation-scan" --quiet
                    rc=$?
                    set -e
                    if [ "$rc" -gt 1 ]; then exit "$rc"; fi
                    python3 - "$WORKSPACE/.preprod/post-remediation-scan/findings.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding='utf-8'))
high = [f for f in data.get('findings', []) if str(f.get('severity','')).upper() in {'HIGH','CRITICAL'}]
if high: raise SystemExit(f'Post-fix scan still has {len(high)} HIGH/CRITICAL finding(s)')
print('Post-fix HIGH/CRITICAL scan is clean')
PY
                '''
                archiveArtifacts artifacts: '.preprod/**/*', allowEmptyArchive: true
            }
        }

        stage('Create remediation PR') {
            when { expression { return params.GENERATE_REMEDIATION } }
            steps {
                withCredentials([string(credentialsId: 'github-token', variable: 'GH_TOKEN')]) {
                    sh '''
                        set -euo pipefail
                        if git diff --quiet; then echo "No source changes; no PR created."; exit 0; fi
                        gh auth setup-git
                        BRANCH="security-remediation/${GIT_COMMIT:0:12}"
                        git checkout -b "$BRANCH"
                        rm -rf .preprod-engine .preprod/baseline-scan .preprod/post-remediation-scan
                        rm -f .preprod-diff.patch .preprod/post-remediation.diff .preprod/scan.patch .preprod/remediation-result.json
                        git config user.name 'pre-prod-tester[bot]'
                        git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
                        git add -A
                        git commit -m 'fix: apply AI security remediation'
                        git push --set-upstream origin "$BRANCH"
                        gh pr create --base "$BASE_BRANCH" --head "$BRANCH" --title 'fix: AI-generated security remediation' --body 'AI-generated remediation validated by scanner and CI.'
                    '''
                }
            }
        }
    }
}