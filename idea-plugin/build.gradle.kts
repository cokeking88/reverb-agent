plugins {
    id("java")
    id("org.jetbrains.kotlin.jvm") version "1.9.22"
    id("org.jetbrains.intellij") version "1.17.2"
}

group = "com.reverb"
version = "1.0-SNAPSHOT"
repositories {
    maven { url = uri("https://maven.aliyun.com/repository/public") }
    maven { url = uri("https://maven.aliyun.com/repository/google") }
    maven { url = uri("https://maven.aliyun.com/repository/gradle-plugin") }
    maven { url = uri("https://cache-redirector.jetbrains.com/www.jetbrains.com/intellij-repository/releases") }
    mavenCentral()
}


dependencies {
    implementation("org.java-websocket:Java-WebSocket:1.5.3")
    implementation("com.google.code.gson:gson:2.10.1")
}

intellij {
    version.set("2023.3.4")
    type.set("IC")
    plugins.set(listOf("java"))
    updateSinceUntilBuild.set(false)
}

tasks {
    withType<JavaCompile> {
        sourceCompatibility = "17"
        targetCompatibility = "17"
    }
    withType<org.jetbrains.kotlin.gradle.tasks.KotlinCompile> {
        kotlinOptions.jvmTarget = "17"
    }

    patchPluginXml {
        sinceBuild.set("233")
        untilBuild.set("243.*")
    }

    // Fat jar configuration to include dependencies
    buildSearchableOptions {
        enabled = false
    }

    jar {
        from(configurations.runtimeClasspath.get().map { if (it.isDirectory) it else zipTree(it) })
        duplicatesStrategy = DuplicatesStrategy.EXCLUDE
    }

    runIde {
        jvmArgs = listOf("-Dreverb.debug=true")
    }
}


