# Guia de Configuração - Battery Analyzer Android App

## Pré-requisitos

### 1. Android Studio
- Versão: **Giraffe 2023.1+** ou mais recente
- Download: https://developer.android.com/studio
- Localização: `/home/roberto/android-studio`

### 2. Android SDK
Instalar via Android Studio SDK Manager:
- **Target SDK**: API 34 (Android 14)
- **Min SDK**: API 26 (Android 8.0)
- **Build Tools**: 34.0.0+
- **Emulator**: Pixel 7 ou superior (recomendado)

### 3. JDK
- Java 17 (incluído no Android Studio)
- Verificar: `java -version` → `17.0.x+`

### 4. Gradle
- Versão: 8.3+ (gerenciado pelo wrapper `gradlew`)

## Instalação Passo a Passo

### Passo 1: Abrir Projeto no Android Studio

```bash
cd /home/roberto/projects/battery-health-analyzer

# Abrir Android Studio com o projeto
/home/roberto/android-studio/bin/studio.sh &
```

No Android Studio:
1. File → Open
2. Navegar até: `/home/roberto/projects/battery-health-analyzer/android`
3. Clicar "Open"
4. Aguardar Gradle sync (primeira vez demora ~5-10 min)

### Passo 2: Configurar SDK

Se Gradle sync falhar:

1. **File → Settings → Languages & Frameworks → Android SDK**
2. **SDK Platforms**:
   - Marcar `Android 14 (API 34)`
   - Marcar `Android 8.0 (API 26)`
   - Clicar **Apply** → **OK**
3. **SDK Tools**:
   - Marcar `Android SDK Platform-Tools`
   - Marcar `Android SDK Tools`
   - Marcar `Google Play Services`
   - Clicar **Apply** → **OK**

### Passo 3: Sincronizar Gradle

1. **File → Sync with Gradle Files**
2. Ou clicar em **Sync Now** se aparecer banner amarelo
3. Aguardar conclusão (watch Gradle console no rodapé)

### Passo 4: Verificar Dependencies

```bash
cd /home/roberto/projects/battery-health-analyzer/android

# Download de dependências
./gradlew dependencies

# Verificar build
./gradlew build
```

## Compilar o App

### Opção 1: Android Studio GUI (Recomendado)

1. **Build → Make Project** (Ctrl+F9)
2. Ou **Build → Build Bundle(s) / APK(s) → Build APK(s)**
3. APK gerado em: `android/app/build/outputs/apk/debug/`

### Opção 2: Terminal

```bash
cd /home/roberto/projects/battery-health-analyzer/android

# Build debug APK
./gradlew assembleDebug

# APK em: build/outputs/apk/debug/app-debug.apk

# Build release APK (requer assinatura)
./gradlew assembleRelease
```

## Executar em Emulador

### Criar Emulador Virtual

1. **Tools → Device Manager** (ou AVD Manager)
2. **Create Virtual Device**
3. Selecionar **(Recommended) Pixel 7** ou Pixel 8
4. Selecionar **API 34 (Android 14)**
5. Nome: `Pixel_7_API34`
6. Clicar **Finish**

### Iniciar Emulador

```bash
# Terminal
cd /home/roberto/android-studio/emulator
./emulator -avd Pixel_7_API34 &

# Ou via Android Studio: Tools → Device Manager → Play
```

### Instalar e Executar App

1. **Emulador rodando** (aguardar boot completo)
2. **Run → Run 'app'** (Shift+F10)
3. Selecionar emulador da lista
4. Clicar **OK**

App será compilado, instalado e iniciado automaticamente.

## Testar em Dispositivo Físico

### 1. Habilitar Developer Mode

- **Abrir Settings → About Phone**
- **Tocar 7x em "Build Number"**
- **Voltar para Settings → Developer Options → USB Debugging ✓**

### 2. Conectar por USB

```bash
# Terminal
adb devices

# Saída esperada:
# List of attached devices
# emulator-5554 device
# RF123ABC device
```

### 3. Permitir USB Debugging

- No telefone: "Allow USB debugging from this computer?" → **Allow**

### 4. Instalar e Executar

No Android Studio:
1. **Run → Run 'app'** (Shift+F10)
2. Selecionar seu dispositivo
3. Clicar **OK**

Ou terminal:
```bash
cd android
adb install build/outputs/apk/debug/app-debug.apk
adb shell am start -n com.souzamonteiro.batteryanalyzer/.ui.MainActivity
```

## Permissões em Runtime

Ao abrir app pela primeira vez:
- Sistema pedirá: **"Battery Analyzer wants to access battery stats"** → Allow
- Confirmar outras permissões conforme solicitado

## Debugar

### Via Android Studio

1. **Run → Debug 'app'** (Shift+F9)
2. Breakpoints: clicar na margem esquerda do código
3. **Debug tab** mostra stack, variáveis, etc

### Logs em Tempo Real

1. **View → Tool Windows → Logcat**
2. Filtrar por: `packageName:com.souzamonteiro.batteryanalyzer`
3. Ou filtrar por level: `W` (warnings), `E` (errors)

```bash
# Terminal
adb logcat | grep "batteryanalyzer"
```

## Troubleshooting

### "Gradle sync failed"

```bash
cd android
./gradlew clean
./gradlew --stop
./gradlew build
```

### "Failed to install APK"

```bash
# Remover app anterior
adb uninstall com.souzamonteiro.batteryanalyzer

# Reinstalar
adb install build/outputs/apk/debug/app-debug.apk
```

### "Device not recognized"

```bash
# Reiniciar adb daemon
adb kill-server
adb start-server
adb devices
```

### "Cannot resolve symbol" errors

- **File → Invalidate Caches and Restart**
- Ou: **Build → Clean Project** → **Build → Make Project**

### App crashes no startup

1. Verificar Logcat para stack trace
2. Confirmar permissões são concedidas
3. Verificar Android Studio logs: **Help → Show Log in Explorer**

## Estrutura de Pastas Importantes

```
android/
├── build.gradle              # Dependências do projeto
├── settings.gradle.kts       # Configuração Gradle
├── src/main/
│   ├── AndroidManifest.xml   # Permissões, componentes
│   ├── java/                 # Código Kotlin
│   └── res/                  # Recursos (strings, themes, layouts)
└── build/
    └── outputs/apk/debug/    # APK gerado (após ./gradlew build)
```

## Próximos Passos

1. ✅ App compila e roda
2. Testar coleta em background (verificar Logcat)
3. Gerar dados (~100+ amostras = ~1.5 horas)
4. Exportar como BDF
5. Usar arquivo CSV na análise web

## Recursos Adicionais

- **Documentação Android**: https://developer.android.com
- **Jetpack Compose**: https://developer.android.com/compose
- **Room Database**: https://developer.android.com/training/data-storage/room
- **Android Services**: https://developer.android.com/guide/components/services

---

**Suporte**: Consultar README.md da pasta `android/`
