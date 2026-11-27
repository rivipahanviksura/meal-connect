import org.openqa.selenium.By;
import org.openqa.selenium.JavascriptExecutor;
import org.openqa.selenium.OutputType;
import org.openqa.selenium.StaleElementReferenceException;
import org.openqa.selenium.TakesScreenshot;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.json.Json;
import org.openqa.selenium.support.ui.ExpectedConditions;
import org.openqa.selenium.support.ui.WebDriverWait;

import org.testng.Assert;
import org.testng.ITestResult;
import org.testng.Reporter;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.DataProvider;
import org.testng.annotations.Test;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

public class SwaggerAuthenticationFlowTest {

    private WebDriver driver;
    private WebDriverWait wait;

    private String accountType;
    private String testEmail;
    private String password;
    private String token;
    private String lastStatus;
    private String lastBody;
    private String lastMethod;
    private String lastPath;

    private WebElement lastOperation;

    private final Json json = new Json();
    private final List<String> secrets = new ArrayList<>();

    private static final String RUN_ID =
            LocalDateTime.now().format(
                    DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss")
            ) + "_" + UUID.randomUUID().toString().substring(0, 8);

    private static final Path EVIDENCE_ROOT = Path.of(
            "target",
            "test-evidence",
            "authentication_" + RUN_ID
    );

    @BeforeMethod(alwaysRun = true)
    public void setup() {
        accountType = null;
        testEmail = null;
        token = null;
        lastStatus = null;
        lastBody = null;
        lastMethod = null;
        lastPath = null;
        lastOperation = null;

        secrets.clear();

        password = "QaTest-" + UUID.randomUUID() + "!";
        secrets.add(password);
        secrets.add(password + "-wrong");

        driver = new ChromeDriver();
        driver.manage().window().maximize();
        driver.manage().timeouts().pageLoadTimeout(
                Duration.ofSeconds(45)
        );

        wait = new WebDriverWait(
                driver,
                Duration.ofSeconds(25)
        );
    }

    private String uniqueId() {
        return UUID.randomUUID().toString().replace("-", "");
    }

    private void openSwagger() {
        lastOperation = null;
        lastStatus = null;
        lastBody = null;

        driver.get(System.getProperty(
                "swagger.url",
                "http://127.0.0.1:8001/docs"
        ));

        wait.until(d ->
                !d.findElements(By.cssSelector(".opblock")).isEmpty()
        );
    }

    private void scrollTo(WebElement element) {
        ((JavascriptExecutor) driver).executeScript(
                "arguments[0].scrollIntoView({block:'center'});",
                element
        );
    }

    private WebElement visible(
            WebElement parent,
            String selector
    ) {
        return wait.until(d -> {
            try {
                for (WebElement element : parent.findElements(
                        By.cssSelector(selector)
                )) {
                    if (element.isDisplayed() && element.isEnabled()) {
                        return element;
                    }
                }
            } catch (StaleElementReferenceException ignored) {
                return null;
            }

            return null;
        });
    }

    private WebElement findOperation(
            String method,
            String path
    ) {
        return wait.until(d -> {
            try {
                for (WebElement operation : d.findElements(
                        By.cssSelector(".opblock")
                )) {
                    List<WebElement> methods = operation.findElements(
                            By.cssSelector(".opblock-summary-method")
                    );

                    List<WebElement> paths = operation.findElements(
                            By.cssSelector(".opblock-summary-path")
                    );

                    if (!methods.isEmpty()
                            && !paths.isEmpty()
                            && method.equals(methods.get(0).getText().trim())
                            && path.equals(paths.get(0).getText().trim())) {
                        return operation;
                    }
                }
            } catch (StaleElementReferenceException ignored) {
                return null;
            }

            return null;
        });
    }

    private void authorize(String accessToken) {
        WebElement button = wait.until(
                ExpectedConditions.elementToBeClickable(
                        By.cssSelector(".auth-wrapper button.authorize")
                )
        );

        scrollTo(button);
        button.click();

        By dialogLocator = By.cssSelector(".dialog-ux");

        wait.until(
                ExpectedConditions.visibilityOfElementLocated(
                        dialogLocator
                )
        );

        WebElement dialog = driver.findElement(dialogLocator);

        for (WebElement candidate : dialog.findElements(
                By.cssSelector("button")
        )) {
            if (candidate.isDisplayed()
                    && candidate.getText().trim()
                    .equalsIgnoreCase("Logout")) {
                candidate.click();
                break;
            }
        }

        // Reacquire the dialog after Swagger updates it.
        dialog = driver.findElement(dialogLocator);

        WebElement input = visible(dialog, "input");
        input.clear();
        input.sendKeys(accessToken);

        visible(dialog, "button.authorize").click();

        wait.until(d -> {
            try {
                return d.findElement(dialogLocator)
                        .getText().contains("Logout");
            } catch (StaleElementReferenceException ignored) {
                return false;
            }
        });

        dialog = driver.findElement(dialogLocator);
        visible(dialog, "button.btn-done").click();

        wait.until(
                ExpectedConditions.invisibilityOfElementLocated(
                        dialogLocator
                )
        );
    }

    private void execute(
            String method,
            String path,
            String requestBody,
            String accessToken
    ) {
        execute(
                method,
                path,
                requestBody,
                accessToken,
                Map.of()
        );
    }

    private void execute(
            String method,
            String path,
            String requestBody,
            String accessToken,
            Map<String, String> pathParameters
    ) {
        lastMethod = method;
        lastPath = path;

        // A fresh page prevents an old response being reused.
        openSwagger();

        if (accessToken != null) {
            authorize(accessToken);
        }

        lastOperation = findOperation(method, path);

        String classes = lastOperation.getAttribute("class");

        if (classes == null || !classes.contains("is-open")) {
            WebElement summary = lastOperation.findElement(
                    By.cssSelector(".opblock-summary")
            );

            scrollTo(summary);
            summary.click();
        }

        WebElement tryButton = visible(
                lastOperation,
                ".try-out__btn"
        );

        scrollTo(tryButton);
        tryButton.click();

        for (Map.Entry<String, String> entry
                : pathParameters.entrySet()) {

            WebElement input = visible(
                    lastOperation,
                    "tr[data-param-name='" + entry.getKey()
                            + "'][data-param-in='path'] input"
            );

            input.clear();
            input.sendKeys(entry.getValue());
        }

        if (requestBody != null) {
            WebElement textarea = visible(
                    lastOperation,
                    "textarea.body-param__text"
            );

            textarea.clear();
            textarea.sendKeys(requestBody);
        }

        WebElement executeButton = visible(
                lastOperation,
                "button.execute"
        );

        scrollTo(executeButton);
        executeButton.click();

        lastStatus = wait.until(d -> {
            try {
                for (WebElement element : lastOperation.findElements(
                        By.cssSelector(
                                ".live-responses-table .response-col_status"
                        )
                )) {
                    String text = element.getText().trim();

                    if (text.matches("(?s)^\\d{3}.*")) {
                        return text.substring(0, 3);
                    }
                }
            } catch (StaleElementReferenceException ignored) {
                return null;
            }

            return null;
        });

        lastBody = wait.until(d -> {
            try {
                for (WebElement element : lastOperation.findElements(
                        By.cssSelector(".live-responses-table pre")
                )) {
                    String text = element.getText().trim();

                    if (!text.isEmpty()) {
                        return text;
                    }
                }
            } catch (StaleElementReferenceException ignored) {
                return null;
            }

            return null;
        });
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> responseObject() {
        return json.toType(lastBody, Map.class);
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> nested(
            Map<String, Object> object,
            String key
    ) {
        Assert.assertTrue(
                object.get(key) instanceof Map,
                "Missing JSON object: " + key
        );

        return (Map<String, Object>) object.get(key);
    }

    private long number(
            Map<String, Object> object,
            String key
    ) {
        Assert.assertTrue(
                object.get(key) instanceof Number,
                "Missing numeric field: " + key
        );

        return ((Number) object.get(key)).longValue();
    }

    private void assertStatus(String expected) {
        Assert.assertEquals(
                lastStatus,
                expected,
                "Unexpected HTTP status for "
                        + lastMethod + " " + lastPath
        );
    }

    private void assertNoPassword() {
        for (String secret : secrets) {
            Assert.assertFalse(
                    lastBody.contains(secret),
                    "Response exposed submitted credentials"
            );
        }

        Assert.assertFalse(
                lastBody.contains("\"password_hash\""),
                "Response exposed a password hash"
        );

        Assert.assertFalse(
                lastBody.contains("\"password\""),
                "Response exposed a password field"
        );
    }

    private void assertError(String expectedCode) {
        Map<String, Object> error = nested(
                responseObject(),
                "error"
        );

        Assert.assertEquals(error.get("code"), expectedCode);

        Assert.assertTrue(
                error.get("message") instanceof String
        );

        Assert.assertFalse(
                ((String) error.get("message")).isBlank()
        );

        Assert.assertTrue(error.get("fields") instanceof List);

        assertNoPassword();
    }

    private String registrationBody(String email) {
        return json.toJson(Map.of(
                "first_name", "Selenium",
                "last_name", "QA",
                "email", email,
                "password", password,
                "account_type", accountType
        ));
    }

    private String loginBody(
            String email,
            String submittedPassword
    ) {
        return json.toJson(Map.of(
                "email", email,
                "password", submittedPassword
        ));
    }

    private void assertRegistration(
            String email,
            String expectedRole
    ) {
        assertStatus("201");

        Map<String, Object> data = nested(
                responseObject(),
                "data"
        );

        Assert.assertEquals(data.get("email"), email);
        Assert.assertEquals(data.get("role"), expectedRole);
        Assert.assertEquals(data.get("account_status"), "active");
        Assert.assertTrue(number(data, "user_id") > 0);

        assertNoPassword();
    }

    private void assertLogin(
            String email,
            String expectedRole
    ) {
        assertStatus("200");

        Map<String, Object> data = nested(
                responseObject(),
                "data"
        );

        Assert.assertEquals(data.get("token_type"), "bearer");
        Assert.assertTrue(number(data, "expires_in") > 0);

        Map<String, Object> user = nested(data, "user");

        Assert.assertEquals(user.get("email"), email);
        Assert.assertEquals(user.get("role"), expectedRole);

        Assert.assertTrue(
                data.get("access_token") instanceof String
        );

        String returnedToken = (String) data.get("access_token");

        Assert.assertFalse(returnedToken.isBlank());

        token = returnedToken;
        secrets.add(returnedToken);

        // Check password exposure separately from the expected token.
        Assert.assertFalse(lastBody.contains(password));
        Assert.assertFalse(lastBody.contains("\"password_hash\""));
        Assert.assertFalse(lastBody.contains("\"password\""));
    }

    private String organizationBody() {
        Map<String, Object> payload = new LinkedHashMap<>();

        payload.put("organization_type", accountType);
        payload.put("name", "MEAL215 Selenium " + accountType);
        payload.put("registration_number", "QA215-" + uniqueId());
        payload.put("contact_email", testEmail);
        payload.put("contact_phone", "+94112345678");
        payload.put("address_line", "123 QA Test Road");
        payload.put("city", "Kurunegala");
        payload.put("district", "Kurunegala");
        payload.put("representative_name", "Selenium QA");
        payload.put("representative_designation", "Owner");

        if ("business".equals(accountType)) {
            payload.put("business_subtype", "restaurant");
            payload.put(
                    "pickup_location",
                    "123 QA Test Road, Kurunegala"
            );
        } else {
            payload.put(
                    "registration_authority",
                    "QA Test Authority"
            );

            payload.put("registration_date", "2020-01-01");

            payload.put("operational_details", Map.of(
                    "operating_area", "Kurunegala",
                    "distribution_area", "Kurunegala",
                    "operational_capability", "Food distribution"
            ));
        }

        return json.toJson(payload);
    }

    @SuppressWarnings("unchecked")
    private void assertOwnDraft(long applicationId) {
        assertStatus("200");

        Map<String, Object> response = responseObject();

        Assert.assertTrue(response.get("data") instanceof List);

        List<?> applications = (List<?>) response.get("data");

        Assert.assertEquals(
                applications.size(),
                1,
                "Expected exactly one application"
        );

        Assert.assertTrue(applications.get(0) instanceof Map);

        Map<String, Object> application =
                (Map<String, Object>) applications.get(0);

        Assert.assertEquals(
                number(application, "application_id"),
                applicationId
        );

        Assert.assertEquals(
                number(application, "organization_id"),
                applicationId
        );

        Assert.assertEquals(application.get("status"), "draft");

        Map<String, Object> details = nested(
                application,
                "draft_details"
        );

        Assert.assertEquals(details.get("contact_email"), testEmail);

        Assert.assertEquals(
                details.get("organization_type"),
                accountType
        );

        Assert.assertEquals(
                number(nested(response, "pagination"), "total_items"),
                1L
        );

        assertNoPassword();
    }

    private String redact(String text) {
        if (text == null) {
            return "";
        }

        String safe = text;

        for (String secret : secrets) {
            if (secret != null && !secret.isBlank()) {
                safe = safe.replace(secret, "[REDACTED]");
            }
        }

        return safe.replaceAll(
                "(\"access_token\"\\s*:\\s*\")[^\"]*(\")",
                "$1[REDACTED_TOKEN]$2"
        );
    }

    private void saveEvidence(
            String step,
            String result
    ) throws Exception {
        Path directory = EVIDENCE_ROOT.resolve(result);
        Files.createDirectories(directory);

        String filename = (
                accountType + "_" + step + "_"
                        + LocalDateTime.now().format(
                        DateTimeFormatter.ofPattern("HHmmss_SSS")
                )
        ).replaceAll("[^a-zA-Z0-9_-]", "_");

        byte[] image;

        List<WebElement> tables = driver.findElements(
                By.cssSelector(
                        ".opblock.is-open .live-responses-table"
                )
        );

        if (!tables.isEmpty()) {
            WebElement table = tables.get(0);

            for (WebElement block : table.findElements(
                    By.cssSelector("pre")
            )) {
                ((JavascriptExecutor) driver).executeScript(
                        "arguments[0].textContent = arguments[1];",
                        block,
                        redact(block.getText())
                );
            }

            scrollTo(table);
            image = table.getScreenshotAs(OutputType.BYTES);
        } else {
            ((JavascriptExecutor) driver).executeScript("""
                document.querySelectorAll('input,textarea')
                  .forEach(e => { e.value = '[REDACTED]'; });

                document.querySelectorAll(
                  '.curl-command,.request-snippets,.auth-container'
                ).forEach(e => {
                  e.style.visibility = 'hidden';
                });

                document.querySelectorAll('pre').forEach(e => {
                  e.textContent = '[REDACTED DIAGNOSTIC CONTENT]';
                });
                """);

            image = ((TakesScreenshot) driver)
                    .getScreenshotAs(OutputType.BYTES);
        }

        Path screenshot = directory.resolve(filename + ".png");
        Files.write(screenshot, image);

        String summary =
                "Scenario: " + accountType + " / " + step + "\n"
                        + "Result: " + result + "\n"
                        + "Time: " + LocalDateTime.now() + "\n"
                        + "Primary QA account: " + testEmail + "\n"
                        + "Request: " + lastMethod + " " + lastPath + "\n"
                        + "HTTP status: " + lastStatus + "\n"
                        + "Response:\n" + redact(lastBody) + "\n";

        Files.writeString(
                directory.resolve(filename + ".txt"),
                summary,
                StandardCharsets.UTF_8
        );

        Reporter.log(
                result + ": " + accountType + " / " + step,
                true
        );

        Reporter.log(
                "Screenshot: " + screenshot.toAbsolutePath(),
                true
        );
    }

    private void verifyStep(
            String step,
            Runnable assertions
    ) throws Exception {
        try {
            assertions.run();
        } catch (AssertionError | RuntimeException failure) {
            try {
                saveEvidence(step, "FAIL");
            } catch (Exception evidenceError) {
                failure.addSuppressed(evidenceError);
            }

            throw failure;
        }

        saveEvidence(step, "PASS");
    }

    @DataProvider(name = "accountTypes", parallel = false)
    public Object[][] accountTypes() {
        return new Object[][]{
                {"business", "business_staff"},
                {"ngo", "ngo_staff"}
        };
    }

    @Test(
            dataProvider = "accountTypes",
            singleThreaded = true
    )
    public void authenticationFlow(
            String type,
            String expectedRole
    ) throws Exception {
        accountType = type;
        testEmail = "qa.selenium." + uniqueId() + "@example.com";

        // 1. Valid registration.
        String registration = registrationBody(testEmail);

        execute(
                "POST",
                "/api/v1/auth/register",
                registration,
                null
        );

        verifyStep(
                "01_registration",
                () -> assertRegistration(testEmail, expectedRole)
        );

        // 2. Duplicate email registration.
        execute(
                "POST",
                "/api/v1/auth/register",
                registration,
                null
        );

        verifyStep("02_duplicate_email", () -> {
            assertStatus("409");
            assertError("ALREADY_EXISTS");
        });

        // 3. Valid login.
        execute(
                "POST",
                "/api/v1/auth/login",
                loginBody(testEmail, password),
                null
        );

        verifyStep(
                "03_valid_login",
                () -> assertLogin(testEmail, expectedRole)
        );

        // 4. Incorrect password.
        execute(
                "POST",
                "/api/v1/auth/login",
                loginBody(testEmail, password + "-wrong"),
                null
        );

        verifyStep("04_wrong_password", () -> {
            assertStatus("401");
            assertError("INVALID_CREDENTIALS");
            Assert.assertFalse(lastBody.contains("access_token"));
        });

        // 5. Registration alone cannot grant organization access.
        execute(
                "GET",
                "/api/v1/donations",
                null,
                token
        );

        verifyStep("05_protected_access_denied", () -> {
            assertStatus("403");
            assertError("FORBIDDEN");
        });

        // 6. Create an organization draft.
        execute(
                "POST",
                "/api/v1/organization-applications",
                organizationBody(),
                token
        );

        verifyStep("06_create_organization_draft", () -> {
            assertStatus("201");

            Map<String, Object> data = nested(
                    responseObject(),
                    "data"
            );

            Assert.assertTrue(number(data, "application_id") > 0);

            Assert.assertEquals(
                    number(data, "application_id"),
                    number(data, "organization_id")
            );

            Assert.assertEquals(data.get("status"), "draft");
            assertNoPassword();
        });

        final long applicationId = number(
                nested(responseObject(), "data"),
                "application_id"
        );

        // 7. View the saved draft.
        execute(
                "GET",
                "/api/v1/organization-applications/me",
                null,
                token
        );

        verifyStep(
                "07_view_own_draft",
                () -> assertOwnDraft(applicationId)
        );

        // 8. A second application from the same account is rejected.
        execute(
                "POST",
                "/api/v1/organization-applications",
                organizationBody(),
                token
        );

        verifyStep("08_duplicate_application_denied", () -> {
            assertStatus("409");
            assertError("ALREADY_EXISTS");
        });

        // 9. Required documents must exist before submission.
        execute(
                "POST",
                "/api/v1/organization-applications/{application_id}/submit",
                null,
                token,
                Map.of(
                        "application_id",
                        Long.toString(applicationId)
                )
        );

        verifyStep("09_missing_documents_denied", () -> {
            assertStatus("422");
            assertError("VALIDATION_ERROR");
        });

        // 10. Failed submission preserves the original draft.
        execute(
                "GET",
                "/api/v1/organization-applications/me",
                null,
                token
        );

        verifyStep(
                "10_failed_submission_preserves_draft",
                () -> assertOwnDraft(applicationId)
        );

        // 11. A draft must not grant protected organization access.
        execute(
                "GET",
                "/api/v1/donations",
                null,
                token
        );

        verifyStep("11_draft_protected_access_denied", () -> {
            assertStatus("403");
            assertError("FORBIDDEN");
        });

        // Create another account for ownership checks.
        final String otherEmail =
                "qa.selenium.other." + uniqueId() + "@example.com";

        // 12. Register the other account.
        execute(
                "POST",
                "/api/v1/auth/register",
                registrationBody(otherEmail),
                null
        );

        verifyStep(
                "12_other_account_registration",
                () -> assertRegistration(otherEmail, expectedRole)
        );

        // 13. Log in as the other account.
        execute(
                "POST",
                "/api/v1/auth/login",
                loginBody(otherEmail, password),
                null
        );

        verifyStep(
                "13_other_account_login",
                () -> assertLogin(otherEmail, expectedRole)
        );

        // 14. Another account cannot submit the original draft.
        execute(
                "POST",
                "/api/v1/organization-applications/{application_id}/submit",
                null,
                token,
                Map.of(
                        "application_id",
                        Long.toString(applicationId)
                )
        );

        verifyStep("14_other_account_cannot_submit", () -> {
            assertStatus("404");
            assertError("NOT_FOUND");
        });

        // 15. Another account must not see the original draft.
        execute(
                "GET",
                "/api/v1/organization-applications/me",
                null,
                token
        );

        verifyStep("15_other_account_cannot_view_draft", () -> {
            assertStatus("200");

            Map<String, Object> response = responseObject();

            Assert.assertTrue(response.get("data") instanceof List);

            Assert.assertTrue(
                    ((List<?>) response.get("data")).isEmpty(),
                    "Another account's draft must not be returned"
            );

            Assert.assertEquals(
                    number(
                            nested(response, "pagination"),
                            "total_items"
                    ),
                    0L
            );

            assertNoPassword();
        });
    }

    @AfterMethod(alwaysRun = true)
    public void closeBrowser(ITestResult result) throws Exception {
        Exception evidenceFailure = null;

        try {
            if (!result.isSuccess() && driver != null) {
                saveEvidence("flow_failure", "FAIL");
            }
        } catch (Exception error) {
            evidenceFailure = error;
        } finally {
            if (driver != null) {
                try {
                    driver.quit();
                } finally {
                    driver = null;
                }
            }
        }

        if (evidenceFailure != null) {
            throw evidenceFailure;
        }
    }
}